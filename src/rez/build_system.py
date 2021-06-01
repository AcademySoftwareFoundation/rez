import os.path

from rez.build_process import BuildType
from rez.exceptions import BuildSystemError
from rez.packages import get_developer_package


def get_buildsys_types():
    """Returns the available build system implementations - cmake, make etc."""
    from rez.plugin_managers import plugin_manager
    return plugin_manager.get_plugins('build_system')


def get_valid_build_systems(working_dir, package=None):
    """Returns the build system classes that could build the source in given dir.

    Args:
        working_dir (str): Dir containing the package definition and potentially
            build files.
        package (`Package`): Package to be built. This may or may not be needed
            to determine the build system. For eg, cmake just has to look for
            a CMakeLists.txt file, whereas the 'build_command' package field
            must be present for the 'custom' build system type.

    Returns:
        List of class: Valid build system class types.
    """
    from rez.plugin_managers import plugin_manager
    from rez.exceptions import PackageMetadataError

    try:
        package = package or get_developer_package(working_dir)
    except PackageMetadataError:
        # no package, or bad package
        pass

    if package:
        if getattr(package, "build_command", None) is not None:
            buildsys_name = "custom"
        else:
            buildsys_name = getattr(package, "build_system", None)

        # package explicitly specifies build system
        if buildsys_name:
            cls = plugin_manager.get_plugin_class('build_system', buildsys_name)
            return [cls]

    # detect valid build systems
    clss = []
    for buildsys_name in get_buildsys_types():
        cls = plugin_manager.get_plugin_class('build_system', buildsys_name)
        if cls.is_valid_root(working_dir, package=package):
            clss.append(cls)

    # Sometimes files for multiple build systems can be present, because one
    # build system uses another (a 'child' build system) - eg, cmake uses
    # make. Detect this case and ignore files from the child build system.
    #
    child_clss = set(x.child_build_system() for x in clss)
    clss = list(set(clss) - child_clss)

    return clss


def create_build_system(working_dir, buildsys_type=None, package=None, opts=None,
                        write_build_scripts=False, verbose=False,
                        build_args=[], child_build_args=[]):
    """Return a new build system that can build the source in working_dir."""
    from rez.plugin_managers import plugin_manager

    # detect build system if necessary
    if not buildsys_type:
        clss = get_valid_build_systems(working_dir, package=package)

        if not clss:
            # Special case - bez. This is an old deprecated build system,
            # which expects a rezbuild.py file. Include info in error showing
            # how to port to a custom build command.
            #
            if os.path.exists(os.path.join(working_dir, "rezbuild.py")):
                msg = (
                    "No build system is associated with the path %s.\n"
                    "\n"
                    "There is a rezbuild.py file present, suggesting you were "
                    "using the deprecated bez build system. You need to use a "
                    "custom build command instead. You can port your existing "
                    "rezbuild.py like so:\n"
                    "\n"
                    "Add this line to package.py:\n"
                    "\n"
                    "    build_command = 'python {root}/rezbuild.py {install}'\n"
                    "\n"
                    "Add these lines to rezbuild.py:\n"
                    "\n"
                    "    if __name__ == '__main__':\n"
                    "        import os, sys\n"
                    "        build(\n"
                    "            source_path=os.environ['REZ_BUILD_SOURCE_PATH'],\n"
                    "            build_path=os.environ['REZ_BUILD_PATH'],\n"
                    "            install_path=os.environ['REZ_BUILD_INSTALL_PATH'],\n"
                    "            targets=sys.argv[1:]\n"
                    "        )"
                )
                raise BuildSystemError(msg % working_dir)

            raise BuildSystemError(
                "No build system is associated with the path %s" % working_dir)

        if len(clss) != 1:
            s = ', '.join(x.name() for x in clss)
            raise BuildSystemError(("Source could be built with one of: %s; "
                                   "Please specify a build system") % s)

        buildsys_type = next(iter(clss)).name()

    # create instance of build system
    cls_ = plugin_manager.get_plugin_class('build_system', buildsys_type)

    return cls_(working_dir,
                opts=opts,
                package=package,
                write_build_scripts=write_build_scripts,
                verbose=verbose,
                build_args=build_args,
                child_build_args=child_build_args)


class BuildSystem(object):
    """A build system, such as cmake, make, Scons etc.
    """
    @classmethod
    def name(cls):
        """Return the name of the build system, eg 'make'."""
        raise NotImplementedError

    def __init__(self, working_dir, opts=None, package=None,
                 write_build_scripts=False, verbose=False, build_args=[],
                 child_build_args=[]):
        """Create a build system instance.

        Args:
            working_dir: Directory to build source from.
            opts: argparse.Namespace object which may contain constructor
                params, as set by our bind_cli() classmethod.
            package (`DeveloperPackage`): Package to build. If None, defaults to
                the package in the working directory.
            write_build_scripts: If True, create build scripts rather than
                perform the full build. The user can then run these scripts to
                place themselves into a build environment and invoke the build
                system directly.
            build_args: Extra cli build arguments.
            child_build_args: Extra cli args for child build system, ignored if
                there is no child build system.
        """
        self.working_dir = working_dir
        if not self.is_valid_root(working_dir):
            raise BuildSystemError(
                "Not a valid working directory for build system %r: %s"
                % (self.name(), working_dir))

        self.package = package or get_developer_package(working_dir)

        self.write_build_scripts = write_build_scripts
        self.build_args = build_args
        self.child_build_args = child_build_args
        self.verbose = verbose

        self.opts = opts

    @classmethod
    def is_valid_root(cls, path):
        """Return True if this build system can build the source in path."""
        raise NotImplementedError

    @classmethod
    def child_build_system(cls):
        """Returns the child build system.

        Some build systems, such as cmake, don't build the source directly.
        Instead, they build an interim set of build scripts that are then
        consumed by a second build system (such as make). You should implement
        this method if that's the case.

        Returns:
            Name of build system (corresponding to the plugin name) if this
            system has a child system, or None otherwise.
        """
        return None

    @classmethod
    def bind_cli(cls, parser, group):
        """Expose parameters to an argparse.ArgumentParser that are specific
        to this build system.

        Args:
            parser (`ArgumentParser`): Arg parser.
            group (`ArgumentGroup`): Arg parser group - you should add args to
                this, NOT to `parser`.
        """
        pass

    def build(self, context, variant, build_path, install_path, install=False,
              build_type=BuildType.local):
        """Implement this method to perform the actual build.

        Args:
            context: A ResolvedContext object that the build process must be
                executed within.
            variant (`Variant`): The variant being built.
            build_path: Where to write temporary build files. May be absolute
                or relative to working_dir.
            install_path (str): The package repository path to install the
                package to, if installing. If None, defaults to
                `config.local_packages_path`.
            install: If True, install the build.
            build_type: A BuildType (i.e local or central).

        Returns:
            A dict containing the following information:
            - success: Bool indicating if the build was successful.
            - extra_files: List of created files of interest, not including
                build targets. A good example is the interpreted context file,
                usually named 'build.rxt.sh' or similar. These files should be
                located under build_path. Rez may install them for debugging
                purposes.
            - build_env_script: If this instance was created with write_build_scripts
                as True, then the build should generate a script which, when run
                by the user, places them in the build environment.
        """
        raise NotImplementedError

    @classmethod
    def get_standard_vars(cls, context, variant, build_type, install,
                          build_path, install_path=None):
        """Returns a standard set of environment variables that can be set
        for the build system to use
        """
        from rez.config import config

        package = variant.parent
        variant_requires = map(str, variant.variant_requires)

        if variant.index is None:
            variant_subpath = ''
        else:
            variant_subpath = variant._non_shortlinked_subpath

        vars_ = {
            'REZ_BUILD_ENV': 1,
            'REZ_BUILD_PATH': build_path,
            'REZ_BUILD_THREAD_COUNT': package.config.build_thread_count,
            'REZ_BUILD_VARIANT_INDEX': variant.index or 0,
            'REZ_BUILD_VARIANT_REQUIRES': ' '.join(variant_requires),
            'REZ_BUILD_VARIANT_SUBPATH': variant_subpath,
            'REZ_BUILD_PROJECT_VERSION': str(package.version),
            'REZ_BUILD_PROJECT_NAME': package.name,
            'REZ_BUILD_PROJECT_DESCRIPTION': (package.description or '').strip(),
            'REZ_BUILD_PROJECT_FILE': package.filepath,
            'REZ_BUILD_SOURCE_PATH': os.path.dirname(package.filepath),
            'REZ_BUILD_REQUIRES': ' '.join(
                str(x) for x in context.requested_packages(True)
            ),
            'REZ_BUILD_REQUIRES_UNVERSIONED': ' '.join(
                x.name for x in context.requested_packages(True)
            ),
            'REZ_BUILD_TYPE': build_type.name,
            'REZ_BUILD_INSTALL': 1 if install else 0,
        }

        if install_path:
            vars_['REZ_BUILD_INSTALL_PATH'] = install_path

        if config.rez_1_environment_variables and \
                not config.disable_rez_1_compatibility and \
                build_type == BuildType.central:
            vars_['REZ_IN_REZ_RELEASE'] = 1

        return vars_

    @classmethod
    def add_standard_build_actions(cls, executor, context, variant, build_type,
                                   install, build_path, install_path=None):
        """Perform build actions common to every build system.
        """
        # set env vars
        env_vars = cls.get_standard_vars(
            context=context,
            variant=variant,
            build_type=build_type,
            install=install,
            build_path=build_path,
            install_path=install_path
        )

        for var, value in env_vars.items():
            executor.env[var] = value

    @classmethod
    def add_pre_build_commands(cls, executor, variant, build_type,
                               install, build_path, install_path=None):
        """Execute pre_build_commands if present.
        """
        from rez.utils.data_utils import RO_AttrDictWrapper

        # bind build-related values into a 'build' namespace
        build_ns = {
            "build_type": build_type.name,
            "install": install,
            "build_path": build_path,
            "install_path": install_path
        }

        # execute pre_build_commands()
        pre_build_commands = getattr(variant, "pre_build_commands")

        if pre_build_commands:
            with executor.reset_globals():
                executor.bind("this", variant)
                executor.bind("build", RO_AttrDictWrapper(build_ns))

                executor.execute_code(pre_build_commands)


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
