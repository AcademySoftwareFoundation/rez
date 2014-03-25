from rez.resources import load_package_metadata, load_package_settings
from rez.build_system import BuildSystem
from rez.resolved_context import ResolvedContext
from rez.exceptions import BuildSystemError, RezError
from rez.util import create_forwarding_script
from rez.shells import create_shell
from rez import plugin_factory
import functools
import subprocess
import platform
import os.path
import os



class RezCMakeError(RezError):
    pass


def _get_cmake_bin():
    exe = BuildSystem.find_executable("cmake")
    try:
        p = subprocess.Popen([exe, "--version"], stdout=subprocess.PIPE)
        stdout,_ = p.communicate()
        vertoks = stdout.strip().split()[-1].split('.')
        ver = (int(vertoks[0]), int(vertoks[1]))
        if ver < (2,8):
            raise BuildSystemError("cmake >= 2.8 required.")
    except:
        pass
    return exe


class CMakeBuildSystem(BuildSystem):
    executable = _get_cmake_bin()
    make_executable = BuildSystem.find_executable("make")

    build_systems = {'eclipse':     "Eclipse CDT4 - Unix Makefiles",
                     'codeblocks':  "CodeBlocks - Unix Makefiles",
                     'make':        "Unix Makefiles",
                     'xcode':       "Xcode"}

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
        build_targets = ["Debug", "Release"]
        parser.add_argument("-b", "--build-target", dest="build_target",
                            type=str, choices=build_targets, default="Release",
                            help="set the build target.")
        parser.add_argument("--bs", "--build-system", dest="build_system",
                            type=str, choices=cls.build_systems.keys(),
                            help="set the cmake build system.")


    def __init__(self, working_dir, opts=None, write_build_scripts=False,
                 verbose=False, build_args=[], child_build_args=[]):
        super(CMakeBuildSystem, self).__init__(working_dir,
                                               opts=opts,
                                               write_build_scripts=write_build_scripts,
                                               verbose=verbose,
                                               build_args=build_args,
                                               child_build_args=child_build_args)
        self.build_target = opts.build_target

        self.cmake_build_system = opts.build_system \
            or self.settings.cmake_build_system
        if self.cmake_build_system == 'xcode' and platform.system() != 'Darwin':
            raise RezCMakeError("Generation of Xcode project only available "
                                "on the OSX platform")

    def build(self, context, build_path, install_path, install=False):
        def _pr(s):
            if self.verbose:
                print s

        # assemble cmake command
        cmd = [self.executable, "-d", self.working_dir]
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

        ext = create_shell().file_extension()
        context_file = os.path.join(build_path, "build.rxt.%s" % ext)
        ret = dict(extra_files=[context_file])

        callback = functools.partial(self._add_build_actions,
                                     context=context,
                                     metadata=self.metadata,
                                     metafile=self.metafile,
                                     settings_=self.settings)

        retcode,_,_ = context.execute_shell(command=cmd,
                                            block=True,
                                            cwd=build_path,
                                            context_filepath=context_file,
                                            actions_callback=callback)
        if retcode:
            ret["success"] = False
            return ret

        if self.write_build_scripts:
            # write out the script that places the user in a build env, where
            # they can run make directly themselves.
            build_env_script = os.path.join(build_path, "build-env.%s" % ext)
            create_forwarding_script(build_env_script,
                                     module="plugins.build_system.cmake",
                                     func_name="_spawn_build_shell",
                                     working_dir=self.working_dir,
                                     build_dir=build_path)
            ret["success"] = True
            ret["build_env_script"] = build_env_script
            return ret

        # assemble make command
        cmd = [self.make_executable]
        cmd += self.child_build_args
        if install and "install" not in cmd:
            cmd.append("install")

        # execute make within the build env
        _pr("\nExecuting: %s" % ' '.join(cmd))
        retcode,_,_ = context.execute_shell(command=cmd,
                                            block=True,
                                            cwd=build_path,
                                            actions_callback=callback)
        ret["success"] = (not retcode)
        return ret

    @staticmethod
    def _add_build_actions(executor, context, metadata, metafile, settings_):
        cmake_path = os.path.join(os.path.dirname(__file__), "cmake_files")
        executor.env.CMAKE_MODULE_PATH.append(cmake_path)
        executor.env.REZ_BUILD_ENV = 1
        #executor.env.REZ_LOCAL_PACKAGES_PATH = settings_.local_packages_path
        #executor.env.REZ_RELEASE_PACKAGES_PATH = settings_.release_packages_path
        executor.env.REZ_BUILD_PROJECT_FILE = metafile
        executor.env.REZ_BUILD_PROJECT_VERSION = metadata.get("version","")
        executor.env.REZ_BUILD_PROJECT_NAME = metadata["name"]
        executor.env.REZ_BUILD_REQUIRES_UNVERSIONED = \
            ' '.join(x.split('-',1)[0] for x in context.requested_packages)



def _spawn_build_shell(working_dir, build_dir):
    # This spawns a shell that the user can run 'make' in directly
    context = ResolvedContext.load(os.path.join(build_dir, "build.rxt"))
    metadata,metafile = load_package_metadata(working_dir)
    settings_ = load_package_settings(metadata)
    settings_.set("prompt", "BUILD>")

    callback = functools.partial(CMakeBuildSystem._add_build_actions,
                                 context=context,
                                 metadata=metadata,
                                 metafile=metafile,
                                 settings_=settings_)

    retcode,_,_ = context.execute_shell(block=True,
                                       cwd=build_dir,
                                       actions_callback=callback)
    sys.exit(retcode)


class CMakeBuildSystemFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return CMakeBuildSystem
