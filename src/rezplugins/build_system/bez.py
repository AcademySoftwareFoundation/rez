"""
Built-in simple python build system
"""
from rez.build_system import BuildSystem
from rez.build_process_ import BuildType
from rez.util import create_forwarding_script
from rez.packages_ import get_developer_package
from rez.resolved_context import ResolvedContext
from rez.config import config
from rez.utils.yaml import dump_yaml
import functools
import os.path
import sys


class BezBuildSystem(BuildSystem):
    """The Bez build system.

    ### DEPRECATED, PLEASE USE CUSTOM BUILD COMMAND INSTEAD ###
    https://github.com/nerdvegas/rez/wiki/Building-Packages#custom-build-commands

    Bez is a simple build system, which runs the 'bez' binary in the build
    environment. All bez does is run the file 'rezbuild.py' (your package's
    build file) in a python subprocess. The code in rezbuild.py has access to
    any python module dependencies of the project.

    Unless told otherwise, Bez expects to find a 'python' executable in the
    build environment. If you have a specific interpreter you want to use, it
    needs to be available as a rez python package, and you should list it as a
    private build requirement in your package.
    """
    @classmethod
    def name(cls):
        return "bez"

    @classmethod
    def is_valid_root(cls, path, package=None):
        return os.path.isfile(os.path.join(path, "rezbuild.py"))

    def __init__(self, working_dir, opts=None, package=None, write_build_scripts=False,
                 verbose=False, build_args=[], child_build_args=[]):
        super(BezBuildSystem, self).__init__(working_dir,
                                             opts=opts,
                                             package=package,
                                             write_build_scripts=write_build_scripts,
                                             verbose=verbose,
                                             build_args=build_args,
                                             child_build_args=child_build_args)

    def build(self, context, variant, build_path, install_path, install=False,
              build_type=BuildType.local):
        # communicate args to bez by placing in a file
        doc = dict(
            source_path=self.working_dir,
            build_path=build_path,
            install_path=install_path,
            build_args=self.build_args)


        ret = {}
        content = dump_yaml(doc)
        bezfile = os.path.join(build_path, ".bez.yaml")
        with open(bezfile, 'w') as f:
            f.write(content + '\n')

        if self.write_build_scripts:
            # write out the script that places the user in a build env, where
            # they can run bez directly themselves.
            build_env_script = os.path.join(build_path, "build-env")
            create_forwarding_script(build_env_script,
                                     module=("build_system", "bez"),
                                     func_name="_FWD__spawn_build_shell",
                                     working_dir=self.working_dir,
                                     build_path=build_path,
                                     variant_index=variant.index,
                                     install=install,
                                     install_path=install_path)

            ret["success"] = True
            ret["build_env_script"] = build_env_script
            return ret

        # run bez in the build environment
        cmd = ["bez"]
        if install and "install" not in cmd:
            cmd.append("install")

        callback = functools.partial(self._add_build_actions,
                                     context=context,
                                     package=self.package,
                                     variant=variant,
                                     build_type=build_type,
                                     install=install,
                                     build_path=build_path,
                                     install_path=install_path)

        retcode, _, _ = context.execute_shell(command=cmd,
                                              block=True,
                                              cwd=build_path,
                                              actions_callback=callback)
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

    callback = functools.partial(BezBuildSystem._add_build_actions,
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
    return BezBuildSystem


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
