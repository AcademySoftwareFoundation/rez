"""
CMake-based build system.
"""
from rez.build_system import BuildSystem
from rez.resolved_context import ResolvedContext
from rez.exceptions import BuildSystemError, RezError
from rez.util import create_forwarding_script
from rez.packages import load_developer_package
from rez.platform_ import platform_
from rez.config import config
from rez.backport.shutilwhich import which
from rez.vendor.schema.schema import Or
from rez.vendor.version.requirement import Requirement
import functools
import subprocess
import platform
import os.path
import sys
import os


class RezCMakeError(BuildSystemError):
    pass


class CMakeBuildSystem(BuildSystem):
    """The CMake build system.

    The 'cmake' executable is run within the build environment. Rez supplies a
    library of cmake macros in the 'cmake_files' directory; these are added to
    cmake's searchpath and are available to use in your own CMakeLists.txt
    file.
    """

    build_systems = {'eclipse':     "Eclipse CDT4 - Unix Makefiles",
                     'codeblocks':  "CodeBlocks - Unix Makefiles",
                     'make':        "Unix Makefiles",
                     'xcode':       "Xcode"}

    build_targets = ["Debug", "Release", "RelWithDebInfo"]

    schema_dict = {
        "build_target":     Or(*build_targets),
        "build_system":     Or(*build_systems.keys()),
        "cmake_args":       [basestring],
        "cmake_binary":     Or(None, basestring)}

    @classmethod
    def name(cls):
        return "cmake"

    @classmethod
    def child_build_system(cls):
        return "make"

    @classmethod
    def is_valid_root(cls, path):
        return os.path.isfile(os.path.join(path, "CMakeLists.txt"))

    @classmethod
    def bind_cli(cls, parser):
        from rez.config import config
        settings = config.plugins.build_system.cmake
        parser.add_argument("--bt", "--build-target", dest="build_target",
                            type=str, choices=cls.build_targets,
                            default=settings.build_target,
                            help="set the build target.")
        parser.add_argument("--bs", "--build-system", dest="build_system",
                            type=str, choices=cls.build_systems.keys(),
                            help="set the cmake build system.")

    def __init__(self, working_dir, opts=None, write_build_scripts=False,
                 verbose=False, build_args=[], child_build_args=[]):
        super(CMakeBuildSystem, self).__init__(
            working_dir,
            opts=opts,
            write_build_scripts=write_build_scripts,
            verbose=verbose,
            build_args=build_args,
            child_build_args=child_build_args)

        self.settings = self.package.config.plugins.build_system.cmake
        self.build_target = opts.build_target or self.settings.build_target
        self.cmake_build_system = opts.build_system \
            or self.settings.build_system
        if self.cmake_build_system == 'xcode' and platform_.name != 'osx':
            raise RezCMakeError("Generation of Xcode project only available "
                                "on the OSX platform")

    def build(self, context, build_path, install_path, install=False):
        def _pr(s):
            if self.verbose:
                print s

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

        # assemble cmake command
        cmd = [found_exe, "-d", self.working_dir]
        cmd += (self.settings.cmake_args or [])
        cmd += self.build_args
        cmd.append("-DCMAKE_INSTALL_PREFIX=%s" % install_path)
        cmd.append("-DCMAKE_MODULE_PATH=${CMAKE_MODULE_PATH}")
        cmd.append("-DCMAKE_BUILD_TYPE=%s" % self.build_target)
        cmd.extend(["-G", self.build_systems[self.cmake_build_system]])

        # execute cmake within the build env
        _pr("Executing: %s" % ' '.join(cmd))
        if not os.path.abspath(build_path):
            build_path = os.path.join(self.working_dir, build_path)
            build_path = os.path.realpath(build_path)

        callback = functools.partial(self._add_build_actions,
                                     context=context,
                                     package=self.package)

        # run the build command and capture/print stderr at the same time
        retcode, _, _ = context.execute_shell(command=cmd,
                                              block=True,
                                              cwd=build_path,
                                              actions_callback=callback)
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
                                     build_dir=build_path)
            ret["success"] = True
            ret["build_env_script"] = build_env_script
            return ret

        # assemble make command
        cmd = ["make"]
        cmd += self.child_build_args
        if install and "install" not in cmd:
            cmd.append("install")

        # execute make within the build env
        _pr("\nExecuting: %s" % ' '.join(cmd))
        retcode, _, _ = context.execute_shell(command=cmd,
                                              block=True,
                                              cwd=build_path,
                                              actions_callback=callback)
        ret["success"] = (not retcode)
        return ret

    @staticmethod
    def _add_build_actions(executor, context, package):
        cmake_path = os.path.join(os.path.dirname(__file__), "cmake_files")
        template_path = os.path.join(os.path.dirname(__file__), "template_files")
        executor.env.CMAKE_MODULE_PATH.append(cmake_path)
        executor.env.REZ_BUILD_DOXYGEN_INCLUDE_PATH = template_path
        executor.env.REZ_BUILD_DOXYGEN_INCLUDE_FILE = 'Doxyfile'
        executor.env.REZ_BUILD_DOXYFILE = os.path.join(template_path, 'Doxyfile')
        executor.env.REZ_BUILD_ENV = 1
        executor.env.REZ_BUILD_VARIANT_NUMBER = get_current_variant_index(context, package)
        executor.env.REZ_BUILD_PROJECT_FILE = package.path
        executor.env.REZ_BUILD_PROJECT_VERSION = str(package.version)
        executor.env.REZ_BUILD_PROJECT_NAME = package.name
        executor.env.REZ_BUILD_PROJECT_DESCRIPTION = package.metadata.get('description', '').strip()
        executor.env.REZ_BUILD_REQUIRES_UNVERSIONED = \
            ' '.join(x.name for x in context.package_requests)
        executor.env.REZ_RELEASE_PACKAGES_PATH = package.config.release_packages_path


def get_current_variant_index(context, package):
    current_variant_index = 0
    current_request_without_implicit_packages = set(context.package_requests).difference(set(context.implicit_packages))

    for index, variant in enumerate(package.iter_variants()):
        request = variant.get_requires(build_requires=True, private_build_requires=True)

        if current_request_without_implicit_packages == set(request):
            current_variant_index = index
            break

    return current_variant_index


def _FWD__spawn_build_shell(working_dir, build_dir):
    # This spawns a shell that the user can run 'make' in directly
    context = ResolvedContext.load(os.path.join(build_dir, "build.rxt"))
    package = load_developer_package(working_dir)
    config.override("prompt", "BUILD>")

    callback = functools.partial(CMakeBuildSystem._add_build_actions,
                                 context=context,
                                 package=package)

    retcode, _, _ = context.execute_shell(block=True,
                                          cwd=build_dir,
                                          actions_callback=callback)
    sys.exit(retcode)


def register_plugin():
    return CMakeBuildSystem
