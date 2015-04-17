"""
CMake-based build system
"""
from rez.build_system import BuildSystem
from rez.build_process_ import BuildType
from rez.resolved_context import ResolvedContext
from rez.exceptions import BuildSystemError
from rez.util import create_forwarding_script
from rez.packages_ import get_developer_package
from rez.utils.platform_ import platform_
from rez.config import config
from rez.backport.shutilwhich import which
from rez.vendor.schema.schema import Or
from rez.shells import create_shell
import functools
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
                     'nmake':       "NMake Makefiles",
                     'xcode':       "Xcode"}

    build_targets = ["Debug", "Release", "RelWithDebInfo"]

    schema_dict = {
        "build_target":     Or(*build_targets),
        "build_system":     Or(*build_systems.keys()),
        "cmake_args":       [basestring],
        "cmake_binary":     Or(None, basestring),
        "make_binary":     Or(None, basestring)}

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
        settings = config.plugins.build_system.cmake
        parser.add_argument("--bt", "--build-target", dest="build_target",
                            type=str, choices=cls.build_targets,
                            default=settings.build_target,
                            help="set the build target (default: %(default)s).")
        parser.add_argument("--bs", "--build-system", dest="build_system",
                            type=str, choices=cls.build_systems.keys(),
                            default=settings.build_system,
                            help="set the cmake build system (default: %(default)s).")

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
        self.cmake_build_system = opts.build_system or self.settings.build_system
        if self.cmake_build_system == 'xcode' and platform_.name != 'osx':
            raise RezCMakeError("Generation of Xcode project only available "
                                "on the OSX platform")

    def build(self, context, variant, build_path, install_path, install=False,
              build_type=BuildType.local):
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

        sh = create_shell()

        # assemble cmake command
        cmd = [found_exe, "-d", self.working_dir]
        cmd += (self.settings.cmake_args or [])
        cmd += (self.build_args or [])
        cmd.append("-DCMAKE_INSTALL_PREFIX=%s" % install_path)
        cmd.append("-DCMAKE_MODULE_PATH=%s" % sh.get_key_token("CMAKE_MODULE_PATH"))
        cmd.append("-DCMAKE_BUILD_TYPE=%s" % self.build_target)
        cmd.append("-DREZ_BUILD_TYPE=%s" % build_type.name)
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

        callback = functools.partial(self._add_build_actions,
                                     context=context,
                                     package=self.package,
                                     variant=variant,
                                     build_type=build_type)

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
                                     build_dir=build_path,
                                     variant_index=variant.index)
            ret["success"] = True
            ret["build_env_script"] = build_env_script
            return ret

        # assemble make command
        if self.settings.make_binary:
            cmd = [self.settings.make_binary]
        else:
            cmd = ["make"]
        cmd += (self.child_build_args or [])

        # execute make within the build env
        _pr("\nExecuting: %s" % ' '.join(cmd))
        retcode, _, _ = context.execute_shell(command=cmd,
                                              block=True,
                                              cwd=build_path,
                                              actions_callback=callback)
        if not retcode and install and "install" not in cmd:
            cmd.append("install")

            # execute make install within the build env
            _pr("\nExecuting: %s" % ' '.join(cmd))
            retcode, _, _ = context.execute_shell(command=cmd,
                                                  block=True,
                                                  cwd=build_path,
                                                  actions_callback=callback)

        ret["success"] = (not retcode)
        return ret

    @staticmethod
    def _add_build_actions(executor, context, package, variant, build_type):
        settings = package.config.plugins.build_system.cmake
        cmake_path = os.path.join(os.path.dirname(__file__), "cmake_files")
        template_path = os.path.join(os.path.dirname(__file__), "template_files")

        executor.env.CMAKE_MODULE_PATH.append(cmake_path)
        executor.env.REZ_BUILD_DOXYFILE = os.path.join(template_path, 'Doxyfile')
        executor.env.REZ_BUILD_ENV = 1
        executor.env.REZ_BUILD_VARIANT_INDEX = variant.index or 0
        # build always occurs on a filesystem package, thus 'filepath' attribute
        # exists. This is not the case for packages in general.
        executor.env.REZ_BUILD_PROJECT_FILE = package.filepath
        executor.env.REZ_BUILD_PROJECT_VERSION = str(package.version)
        executor.env.REZ_BUILD_PROJECT_NAME = package.name
        executor.env.REZ_BUILD_PROJECT_DESCRIPTION = \
            (package.description or '').strip()
        executor.env.REZ_BUILD_REQUIRES_UNVERSIONED = \
            ' '.join(x.name for x in context.requested_packages(True))
        value = '1' if settings.install_pyc else '0'
        executor.env.REZ_BUILD_INSTALL_PYC = value

        if config.rez_1_environment_variables and \
                not config.disable_rez_1_compatibility and \
                build_type == BuildType.central:
            executor.env.REZ_IN_REZ_RELEASE = 1


def _FWD__spawn_build_shell(working_dir, build_dir, variant_index):
    # This spawns a shell that the user can run 'make' in directly
    context = ResolvedContext.load(os.path.join(build_dir, "build.rxt"))
    package = get_developer_package(working_dir)
    variant = package.get_variant(variant_index)
    config.override("prompt", "BUILD>")

    callback = functools.partial(CMakeBuildSystem._add_build_actions,
                                 context=context,
                                 package=package,
                                 variant=variant,
                                 build_type=BuildType.local)

    retcode, _, _ = context.execute_shell(block=True,
                                          cwd=build_dir,
                                          actions_callback=callback)
    sys.exit(retcode)


def register_plugin():
    return CMakeBuildSystem
