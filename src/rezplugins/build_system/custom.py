# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Package-defined build command
"""
from __future__ import annotations

from shlex import quote
from typing import TYPE_CHECKING
import functools
import os.path
import sys
import os

from rez.build_system import BuildSystem, BuildResult
from rez.build_process import BuildType
from rez.utils.execution import create_forwarding_script
from rez.packages import get_developer_package, Variant
from rez.resolved_context import ResolvedContext
from rez.shells import create_shell
from rez.exceptions import PackageMetadataError
from rez.utils.colorize import heading, Printer
from rez.utils.logging_ import print_warning
from rez.config import config

if TYPE_CHECKING:
    import argparse
    from rez.rex import RexExecutor


class CustomBuildSystem(BuildSystem):
    """This build system runs the 'build_command' defined in a package.py.

    For example, consider the package.py snippet:

        build_commands = "bash {root}/build.sh {install}"

    This will run the given bash command in the build path - this is typically
    located somewhere under the 'build' dir under the root dir containing the
    package.py.

    The following variables are available for expansion:

    * root: The source directory (the one containing the package.py).
    * install: 'install' if an install is occurring, or the empty string ('')
      otherwise;
    * build_path: The build path (this will also be the cwd);
    * install_path: Full path to install destination;
    * name: Name of the package getting built;
    * variant_index: Index of the current variant getting built, or an empty
      string ('') if no variants are present.
    * version: Package version currently getting built.
    """

    @classmethod
    def name(cls):
        return "custom"

    @classmethod
    def is_valid_root(cls, path, package=None):
        if package is None:
            try:
                package = get_developer_package(path)
            except PackageMetadataError:
                return False

        return (getattr(package, "build_command", None) is not None)

    def __init__(self, working_dir, opts=None, package=None, write_build_scripts=False,
                 verbose=False, build_args=[], child_build_args=[]):
        super(CustomBuildSystem, self).__init__(
            working_dir,
            opts=opts,
            package=package,
            write_build_scripts=write_build_scripts,
            verbose=verbose,
            build_args=build_args,
            child_build_args=child_build_args)

    @classmethod
    def bind_cli(cls, parser: argparse.ArgumentParser, group: argparse._ArgumentGroup):
        """
        Uses a 'parse_build_args.py' file to add options, if found.
        """
        try:
            with open("./parse_build_args.py") as f:
                source = f.read()
        except:
            return

        # detect what extra args have been added
        before_args = set(x.dest for x in parser._actions)

        try:
            exec(source, {"parser": group})
        except Exception as e:
            print_warning("Error in ./parse_build_args.py: %s" % str(e))

        after_args = set(x.dest for x in parser._actions)
        extra_args = after_args - before_args

        # store extra args onto parser so we can get to it in self.build()
        setattr(parser, "_rezbuild_extra_args", list(extra_args))

    def build(self,
              context: ResolvedContext,
              variant: Variant,
              build_path: str,
              install_path: str,
              install: bool = False,
              build_type=BuildType.local) -> BuildResult:
        """Perform the build.

        Note that most of the func args aren't used here - that's because this
        info is already passed to the custom build command via environment
        variables.
        """
        ret = BuildResult()

        if self.write_build_scripts:
            # write out the script that places the user in a build env
            build_env_script = os.path.join(build_path, "build-env")
            create_forwarding_script(
                build_env_script,
                module=("build_system", "custom"),
                func_name="_FWD__spawn_build_shell",
                working_dir=self.working_dir,
                build_path=build_path,
                variant_index=variant.index,
                install=install,
                install_path=install_path
            )

            ret["success"] = True
            ret["build_env_script"] = build_env_script
            return ret

        # get build command
        command = self.package.build_command

        # False just means no build command
        if command is False:
            ret["success"] = True
            return ret

        def expand(txt):
            # we need a shell here because build_command may reference vars like
            # {root}, and that may require path normalization.
            sh = create_shell()

            return txt.format(
                build_path=sh.normalize_path(build_path),
                install_path=sh.normalize_path(install_path),
                root=sh.normalize_path(self.package.root),
                install="install" if install else '',
                name=self.package.name,
                variant_index=variant.index if variant.index is not None else '',
                version=self.package.version
            ).strip()

        if isinstance(command, str):
            if self.build_args:
                command = command + ' ' + ' '.join(map(quote, self.build_args))

            command = expand(command)
            cmd_str = command
        else:  # list
            command = command + self.build_args
            command = list(map(expand, command))
            cmd_str = ' '.join(map(quote, command))

        if self.verbose:
            pr = Printer(sys.stdout)
            pr("Running build command: %s" % cmd_str, heading)

        # run the build command
        post_actions_callback = functools.partial(
            self.add_pre_build_commands,
            variant=variant,
            build_type=build_type,
            install=install,
            build_path=build_path,
            install_path=install_path
        )

        def _actions_callback(executor):
            self._add_build_actions(
                executor,
                context=context,
                package=self.package,
                variant=variant,
                build_type=build_type,
                install=install,
                build_path=build_path,
                install_path=install_path
            )

            if self.opts:
                # write args defined in ./parse_build_args.py out as env vars
                extra_args = getattr(self.opts.parser, "_rezbuild_extra_args", [])

                for key, value in list(vars(self.opts).items()):
                    if key in extra_args:
                        varname = "__PARSE_ARG_%s" % key.upper()

                        # do some value conversions
                        if isinstance(value, bool):
                            value = 1 if value else 0
                        elif isinstance(value, (list, tuple)):
                            value = list(map(str, value))
                            value = list(map(quote, value))
                            value = ' '.join(value)

                        executor.env[varname] = value

        retcode, _, _ = context.execute_shell(
            command=command,
            block=True,
            cwd=build_path,
            actions_callback=_actions_callback,
            post_actions_callback=post_actions_callback
        )

        ret["success"] = (not retcode)
        return ret

    @classmethod
    def _add_build_actions(cls, executor: RexExecutor, context: ResolvedContext, package, variant,
                           build_type, install, build_path, install_path=None):
        cls.add_standard_build_actions(
            executor=executor,
            context=context,
            variant=variant,
            build_type=build_type,
            install=install,
            build_path=build_path,
            install_path=install_path
        )


def _FWD__spawn_build_shell(working_dir, build_path, variant_index, install,
                            install_path=None):
    # This spawns a shell that the user can run the build command in directly
    context = ResolvedContext.load(os.path.join(build_path, "build.rxt"))
    package = get_developer_package(working_dir)
    variant = package.get_variant(variant_index)
    config.override("prompt", "BUILD>")

    actions_callback = functools.partial(
        CustomBuildSystem._add_build_actions,
        context=context,
        package=package,
        variant=variant,
        build_type=BuildType.local,
        install=install,
        build_path=build_path,
        install_path=install_path
    )

    post_actions_callback = functools.partial(
        CustomBuildSystem.add_pre_build_commands,
        variant=variant,
        build_type=BuildType.local,
        install=install,
        build_path=build_path,
        install_path=install_path
    )

    retcode, _, _ = context.execute_shell(
        block=True,
        cwd=build_path,
        actions_callback=actions_callback,
        post_actions_callback=post_actions_callback
    )

    sys.exit(retcode)


def register_plugin():
    return CustomBuildSystem
