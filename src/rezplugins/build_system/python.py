"""
Built-in simple python build system
"""
import os
import glob
import shutil
import subprocess
import sys
import functools
import argparse
from pipes import quote

from rez.build_system import BuildSystem
from rez.build_process_ import BuildType
from rez.util import create_forwarding_script
from rez.packages_ import get_developer_package
from rez.resolved_context import ResolvedContext
from rez.config import config
from rez.utils.colorize import heading, Printer
from rez.utils.yaml import dump_yaml


class PythonBuildSystem(BuildSystem):
    """The standard python setup.py build system.

    This is a wrapper around the normal python setup.py build system.  It
    allows python projects to seamlessly build using rez without having to
    create a cmake or bez build wrapper.

    """
    @classmethod
    def name(cls):
        return "python"

    @classmethod
    def is_valid_root(cls, path):
        return (os.path.isfile(os.path.join(path, "setup.py"))
                and not os.path.isfile(os.path.join(path, "rezbuild.py")))

    def __init__(self, working_dir, opts=None, package=None, write_build_scripts=False,
                 verbose=False, build_args=[], child_build_args=[]):
        super(PythonBuildSystem, self).__init__(
            working_dir,
            opts=opts,
            package=package,
            write_build_scripts=write_build_scripts,
            verbose=verbose,
            build_args=build_args,
            child_build_args=child_build_args)

    @classmethod
    def bind_cli(cls, parser):
        """
        Uses a 'parse_build_args.py' file to add options, if found.
        """
        try:
            with open("./parse_build_args.py") as f:
                source = f.read()
        except Exception as e:
            return

        # detect what extra args have been added
        before_args = set(x.dest for x in parser._actions)

        try:
            exec source in {"parser": parser}
        except Exception as e:
            print_warning("Error in ./parse_build_args.py: %s" % str(e))

        after_args = set(x.dest for x in parser._actions)
        extra_args = after_args - before_args

        # store extra args onto parser so we can get to it in self.build()
        setattr(parser, "_rezbuild_extra_args", list(extra_args))

    def build(self, context, variant, build_path, install_path, install=False,
              build_type=BuildType.local):
        """Perform the build.

        Note that most of the func args aren't used here - that's because this
        info is already passed to the custom build command via environment
        variables.
        """
        ret = {}
        if self.write_build_scripts:
            # write out the script that places the user in a build env, where
            # they can run bez directly themselves.
            build_env_script = os.path.join(build_path, "build-env")
            create_forwarding_script(build_env_script,
                                     module=("build_system", self.name),
                                     func_name="_FWD__spawn_build_shell",
                                     working_dir=self.working_dir,
                                     build_path=build_path,
                                     variant_index=variant.index,
                                     install=install,
                                     install_path=install_path)

            ret["success"] = True
            ret["build_env_script"] = build_env_script
            return ret

        # run the build command
        def _make_callack(env=None):
            def _callback(executor):
                self._add_build_actions(executor,
                                        context=context,
                                        package=self.package,
                                        variant=variant,
                                        build_type=build_type,
                                        install=install,
                                        build_path=build_path,
                                        install_path=install_path)

                if self.opts:
                    # write args defined in ./parse_build_args.py out as env vars
                    extra_args = getattr(self.opts.parser, "_rezbuild_extra_args", [])

                    for key, value in vars(self.opts).iteritems():
                        if key in extra_args:
                            varname = "__PARSE_ARG_%s" % key.upper()

                            # do some value conversions
                            if isinstance(value, bool):
                                value = 1 if value else 0
                            elif isinstance(value, (list, tuple)):
                                value = map(str, value)
                                value = map(quote, value)
                                value = ' '.join(value)

                            executor.env[varname] = value

                if env:
                    for key, value in env.items():
                        if isinstance(value, (list, tuple)):
                            for path_ in value:
                                executor.env[key].append(path_)
                        else:
                            executor.env[key] = value

            return _callback

        build_arg_parser = argparse.ArgumentParser()
        build_arg_parser.add_argument('--develop')

        build_args = self.build_args or []
        install_mode = install
        develop_mode = 'develop' in build_args
        pip_mode = 'pip' not in build_args

        source_path = self.working_dir
        py_install_root = os.path.join(source_path, 'build', '_py_install')
        py_develop_root = os.path.join(source_path, 'build', '_py_develop')
        dist_root = os.path.join(source_path, 'dist')
        setup_py = os.path.join(source_path, 'setup.py')
        prefix = 'rez'

        def _run_context_shell(command, cwd, env=None):
            _callback = _make_callack(env)
            retcode, _, _ = context.execute_shell(command=command,
                                                  block=True,
                                                  cwd=cwd,
                                                  parent_environ=None,
                                                  actions_callback=_callback)
            return retcode

        def _copy_tree(src, dest):
            # Utility function to copy tree.
            if os.path.exists(dest):
                shutil.rmtree(dest)
            if os.path.exists(src):
                shutil.copytree(src, dest)

        def _setup_py_build():
            cmds = ['python', setup_py, 'install', '--root', py_install_root, '--prefix', prefix, '-f']
            # subprocess.call(cmds, cwd=source_path)
            return _run_context_shell(cmds, cwd=source_path)

        def _pip_build():
            #TODO: pip 10 will install wheel builds by default, making this intermediate wheel build step unnecessary
            # Generate wheel
            print('Building wheel...')
            pip = 'pip'
            # These args speed up pip builds
            pip_args = ['--disable-pip-version-check', '--no-deps', '--no-index']
            cmds = [pip, 'wheel', '.', '-w', dist_root] + pip_args
            # subprocess.call(cmds, cwd=source_path)
            _run_context_shell(cmds, cwd=source_path)

            # Install wheel that we just built
            print('Installing wheel...')
            wheel_path = glob.glob(os.path.join(dist_root, '*.whl'))[0]
            cmds = [pip, 'install', wheel_path, '--root', py_install_root, '--prefix', prefix] + pip_args
            # subprocess.call(cmds, cwd=source_path)
            return _run_context_shell(cmds, cwd=source_path)

        def _build():
            # Clear out old python builds
            if os.path.exists(py_install_root):
                shutil.rmtree(py_install_root)
            if os.path.isdir(dist_root):
                shutil.rmtree(dist_root)

            if pip_mode:
                retcode = _pip_build()
            else:
                retcode = _setup_py_build()

            # Move/Copy build files into rez-build directory
            _copy_tree(
                os.path.join(py_install_root, prefix, 'Lib', 'site-packages'),
                os.path.join(build_path, 'python')
            )
            _copy_tree(
                os.path.join(py_install_root, prefix, 'Scripts'),
                os.path.join(build_path, 'bin')
            )
            return retcode

        def _develop():
            # Clear out old develop builds
            if os.path.exists(py_develop_root):
                shutil.rmtree(py_develop_root)

            # Create develop locations, required by setuptools
            python_dir = os.path.join(py_develop_root, 'python')
            bin_dir = os.path.join(py_develop_root, 'bin')
            os.makedirs(python_dir)
            os.makedirs(bin_dir)

            # Temporarily add develop install location to PYTHONPATH, otherwise
            # setuptools will refuse to create .pth files inside the develop python directory.
            env = {'PYTHONPATH': [python_dir]}
            # Run normal python setup develop command
            cmds = ['python', setup_py, 'develop', '-d', python_dir, '-s', bin_dir]
            # subprocess.call(cmds, cwd=source_path, env=env)
            retcode = _run_context_shell(cmds, cwd=source_path, env=env)

            # Move/Copy develop files into rez-build directory
            _copy_tree(
                os.path.join(py_develop_root, 'python'),
                os.path.join(build_path, 'python')
            )
            _copy_tree(
                os.path.join(py_develop_root, 'bin'),
                os.path.join(build_path, 'bin')
            )
            return retcode

        def _install():
            # Copy build to install location
            for name in ['python', 'bin']:
                _copy_tree(
                    src=os.path.join(build_path, name),
                    dest=os.path.join(install_path, name)
                )

        if self.verbose:
            pr = Printer(sys.stdout)
            pr('Running setup.py build...')

        if develop_mode:
            retcode = _develop()
        else:
            retcode = _build()

        if install_mode:
            _install()

        ret["success"] = (not retcode)
        return ret

    @classmethod
    def _add_build_actions(cls, executor, context, package, variant,
                           build_type, install, build_path, install_path=None):
        cls.set_standard_vars(executor=executor,
                              context=context,
                              variant=variant,
                              build_type=build_type,
                              install=install,
                              build_path=build_path,
                              install_path=install_path)


def _FWD__spawn_build_shell(working_dir, build_path, variant_index, install,
                            install_path=None):
    # This spawns a shell that the user can run 'bez' in directly
    context = ResolvedContext.load(os.path.join(build_path, "build.rxt"))
    package = get_developer_package(working_dir)
    variant = package.get_variant(variant_index)
    config.override("prompt", "BUILD>")

    callback = functools.partial(PythonBuildSystem._add_build_actions,
                                 context=context,
                                 package=package,
                                 variant=variant,
                                 build_type=BuildType.local,
                                 install=install,
                                 build_path=build_path,
                                 install_path=install_path)

    retcode, _, _ = context.execute_shell(block=True, cwd=build_path,
                                          actions_callback=callback)
    sys.exit(retcode)


def register_plugin():
    return PythonBuildSystem


# Copyright 2018 Brendan Abel
# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
