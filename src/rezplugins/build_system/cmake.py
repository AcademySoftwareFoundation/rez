"""
CMake-based build system
"""
from __future__ import print_function

from rez.build_system import BuildSystem
from rez.build_process import BuildType
from rez.resolved_context import ResolvedContext
from rez.exceptions import BuildSystemError
from rez.utils.execution import create_forwarding_script
from rez.packages import get_developer_package
from rez.utils.platform_ import platform_
from rez.config import config
from rez.backport.shutilwhich import which
from rez.vendor.schema.schema import Or
from rez.vendor.six import six
from rez.shells import create_shell
import functools
import os.path
import sys
import os


basestring = six.string_types[0]


class RezCMakeError(BuildSystemError):
    pass


class CMakeBuildSystem(BuildSystem):
    """The CMake build system.

    The 'cmake' executable is run within the build environment. Rez supplies a
    library of cmake macros in the 'cmake_files' directory; these are added to
    cmake's searchpath and are available to use in your own CMakeLists.txt
    file.

    The following CMake variables are available:
    - REZ_BUILD_TYPE: One of 'local', 'central'. Describes whether an install
      is going to the local packages path, or the release packages path.
    - REZ_BUILD_INSTALL: One of 0 or 1. If 1, an installation is taking place;
      if 0, just a build is occurring.
    """

    build_systems = {
        'eclipse': "Eclipse CDT4 - Unix Makefiles",
        'codeblocks': "CodeBlocks - Unix Makefiles",
        'make': "Unix Makefiles",
        'nmake': "NMake Makefiles",
        'mingw': "MinGW Makefiles",
        'xcode': "Xcode",
        'ninja': "Ninja",
    }

    build_targets = ["Debug", "Release", "RelWithDebInfo"]

    schema_dict = {
        "build_target": Or(*build_targets),
        "build_system": Or(*list(build_systems.keys())),
        "cmake_args": [basestring],
        "cmake_binary": Or(None, basestring),
        "make_binary": Or(None, basestring)
    }

    @classmethod
    def name(cls):
        return "cmake"

    @classmethod
    def child_build_system(cls):
        return "make"

    @classmethod
    def is_valid_root(cls, path, package=None):
        return os.path.isfile(os.path.join(path, "CMakeLists.txt"))

    @classmethod
    def bind_cli(cls, parser, group):
        settings = config.plugins.build_system.cmake
        group.add_argument("--bt", "--build-target", dest="build_target",
                           type=str, choices=cls.build_targets,
                           default=settings.build_target,
                           help="set the build target (default: %(default)s).")
        group.add_argument("--bs", "--cmake-build-system",
                           dest="cmake_build_system",
                           choices=list(cls.build_systems.keys()),
                           default=settings.build_system,
                           help="set the cmake build system (default: %(default)s).")

    def __init__(self, working_dir, opts=None, package=None, write_build_scripts=False,
                 verbose=False, build_args=[], child_build_args=[]):
        super(CMakeBuildSystem, self).__init__(
            working_dir,
            opts=opts,
            package=package,
            write_build_scripts=write_build_scripts,
            verbose=verbose,
            build_args=build_args,
            child_build_args=child_build_args)

        self.settings = self.package.config.plugins.build_system.cmake
        self.build_target = getattr(opts, "build_target", self.settings.build_target)
        self.cmake_build_system = getattr(opts, "cmake_build_system", self.settings.build_system)

        if self.cmake_build_system == 'xcode' and platform_.name != 'osx':
            raise RezCMakeError("Generation of Xcode project only available "
                                "on the OSX platform")

    def build(self, context, variant, build_path, install_path, install=False,
              build_type=BuildType.local):
        def _pr(s):
            if self.verbose:
                print(s)

        # find cmake binary
        if self.settings.cmake_binary:
            exe = self.settings.cmake_binary
        else:
            exe = context.which("cmake", fallback=True)
        if not exe:
            raise RezCMakeError("could not find cmake binary")
        found_exe = which(exe)
        if not found_exe:
            raise RezCMakeError("cmake binary does not exist: %s" % exe)

        sh = create_shell()

        # assemble cmake command
        cmd = [found_exe]
        # cmd.append("-d")  # see https://github.com/nerdvegas/rez/issues/1055
        cmd.append(self.working_dir)

        cmd += (self.settings.cmake_args or [])
        cmd += (self.build_args or [])

        cmd.append("-DCMAKE_INSTALL_PREFIX=%s" % install_path)
        cmd.append("-DCMAKE_MODULE_PATH=%s" %
                   sh.get_key_token("CMAKE_MODULE_PATH").replace('\\', '/'))
        cmd.append("-DCMAKE_BUILD_TYPE=%s" % self.build_target)
        cmd.append("-DREZ_BUILD_TYPE=%s" % build_type.name)
        cmd.append("-DREZ_BUILD_INSTALL=%d" % (1 if install else 0))
        cmd.extend(["-G", self.build_systems[self.cmake_build_system]])

        if config.rez_1_cmake_variables and \
                not config.disable_rez_1_compatibility and \
                build_type == BuildType.central:
            cmd.append("-DCENTRAL=1")

        # execute cmake within the build env
        _pr("Executing: %s" % ' '.join(cmd))
        if not os.path.abspath(build_path):
            build_path = os.path.join(self.working_dir, build_path)
            build_path = os.path.realpath(build_path)

        actions_callback = functools.partial(
            self._add_build_actions,
            context=context,
            package=self.package,
            variant=variant,
            build_type=build_type,
            install=install,
            build_path=build_path,
            install_path=install_path
        )

        post_actions_callback = functools.partial(
            self.add_pre_build_commands,
            variant=variant,
            build_type=build_type,
            install=install,
            build_path=build_path,
            install_path=install_path
        )

        # run the build command and capture/print stderr at the same time
        retcode, _, _ = context.execute_shell(
            command=cmd,
            block=True,
            cwd=build_path,
            actions_callback=actions_callback,
            post_actions_callback=post_actions_callback
        )

        ret = {}
        if retcode:
            ret["success"] = False
            return ret

        if self.write_build_scripts:
            # write out the script that places the user in a build env, where
            # they can run make directly themselves.
            build_env_script = os.path.join(build_path, "build-env")
            create_forwarding_script(build_env_script,
                                     module=("build_system", "cmake"),
                                     func_name="_FWD__spawn_build_shell",
                                     working_dir=self.working_dir,
                                     build_path=build_path,
                                     variant_index=variant.index,
                                     install=install,
                                     install_path=install_path)
            ret["success"] = True
            ret["build_env_script"] = build_env_script
            return ret

        # assemble make command
        make_binary = self.settings.make_binary

        if not make_binary:
            if self.cmake_build_system == "mingw":
                make_binary = "mingw32-make"
            elif self.cmake_build_system == "nmake":
                make_binary = "nmake"
            elif self.cmake_build_system == "ninja":
                make_binary = "ninja"
            else:
                make_binary = "make"

        cmd = [make_binary] + (self.child_build_args or [])

        # nmake has no -j
        if make_binary != "nmake":
            if not any(x.startswith("-j") for x in (self.child_build_args or [])):
                n = variant.config.build_thread_count
                cmd.append("-j%d" % n)

        # execute make within the build env
        _pr("\nExecuting: %s" % ' '.join(cmd))
        retcode, _, _ = context.execute_shell(
            command=cmd,
            block=True,
            cwd=build_path,
            actions_callback=actions_callback,
            post_actions_callback=post_actions_callback
        )

        if not retcode and install and "install" not in cmd:
            cmd.append("install")

            # execute make install within the build env
            _pr("\nExecuting: %s" % ' '.join(cmd))
            retcode, _, _ = context.execute_shell(
                command=cmd,
                block=True,
                cwd=build_path,
                actions_callback=actions_callback,
                post_actions_callback=post_actions_callback
            )

        ret["success"] = (not retcode)
        return ret

    @classmethod
    def _add_build_actions(cls, executor, context, package, variant,
                           build_type, install, build_path, install_path=None):
        settings = package.config.plugins.build_system.cmake
        cmake_path = os.path.join(os.path.dirname(__file__), "cmake_files")
        template_path = os.path.join(os.path.dirname(__file__), "template_files")

        cls.add_standard_build_actions(
            executor=executor,
            context=context,
            variant=variant,
            build_type=build_type,
            install=install,
            build_path=build_path,
            install_path=install_path
        )

        executor.env.CMAKE_MODULE_PATH.append(cmake_path.replace('\\', '/'))
        executor.env.REZ_BUILD_DOXYFILE = os.path.join(template_path, 'Doxyfile')
        executor.env.REZ_BUILD_INSTALL_PYC = '1' if settings.install_pyc else '0'


def _FWD__spawn_build_shell(working_dir, build_path, variant_index, install,
                            install_path=None):
    # This spawns a shell that the user can run 'make' in directly
    context = ResolvedContext.load(os.path.join(build_path, "build.rxt"))
    package = get_developer_package(working_dir)
    variant = package.get_variant(variant_index)
    config.override("prompt", "BUILD>")

    actions_callback = functools.partial(
        CMakeBuildSystem._add_build_actions,
        context=context,
        package=package,
        variant=variant,
        build_type=BuildType.local,
        install=install,
        build_path=build_path,
        install_path=install_path
    )

    post_actions_callback = functools.partial(
        CMakeBuildSystem.add_pre_build_commands,
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
    return CMakeBuildSystem


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
