"""
Builds packages on local host
"""
from rez.build_process_ import BuildProcessHelper, BuildType
from rez.exceptions import BuildError
import shutil
import os


class LocalBuildProcess(BuildProcessHelper):
    """The default build process.

    This process builds a package's variants sequentially and on localhost.
    """
    @classmethod
    def name(cls):
        return "local"

    def build(self, install_path=None, clean=False, install=False, variants=None):
        self._print_header("Building %s..." % self.package.qualified_name)

        num_visited, build_env_scripts = self.visit_variants(
            self._build_variant,
            build_type=BuildType.local,
            variants=variants,
            install_path=install_path,
            clean=clean,
            install=install)

        if None not in build_env_scripts:
            self._print("\nThe following executable script(s) have been created:")
            self._print('\n'.join(build_env_scripts))
            self._print('')
        else:
            self._print("\nAll %d build(s) were successful.\n", num_visited)

    def release(self, release_message=None, variants=None):
        self._print_header("Releasing %s..." % self.package.qualified_name)
        self.visit_variants(self._release_variant,
                            variants=variants,
                            release_message=release_message)

    def _build_variant_base(self, variant, build_type, install_path=None,
                            clean=False, install=False, **kwargs):
        self._print_header("Building variant %s..." % self._n_of_m(variant))

        # create build/install paths
        install_path = install_path or self.package.config.local_packages_path
        variant_install_path = self.get_package_install_path(install_path)
        variant_build_path = self.build_path
        if variant.subpath:
            variant_build_path = os.path.join(variant_build_path, variant.subpath)
            variant_install_path = os.path.join(variant_install_path, variant.subpath)

        if clean and os.path.exists(variant_build_path):
            shutil.rmtree(variant_build_path)
        if not os.path.exists(variant_build_path):
            os.makedirs(variant_build_path)

        if install and not os.path.exists(variant_install_path):
            os.makedirs(variant_install_path)

        # create build environment
        context, rxt_filepath = self.create_build_context(
            variant=variant,
            build_type=build_type,
            build_path=variant_build_path)

        # run build system
        build_system_name = self.build_system.name()
        self._print("\nInvoking %s build system...", build_system_name)
        build_result = self.build_system.build(
            context,
            build_path=variant_build_path,
            install_path=variant_install_path,
            install=install,
            build_type=build_type)

        if not build_result.get("success"):
            raise BuildError("The %s build system failed" % build_system_name)

        if install:
            # install some files for debugging purposes
            extra_files = build_result.get("extra_files", []) + [rxt_filepath]
            for file_ in extra_files:
                shutil.copy(file_, variant_install_path)

        return build_result

    def _build_variant(self, variant, build_type, install_path=None,
                       clean=False, install=False, **kwargs):
        build_result = self._build_variant_base(build_type=build_type,
                                                variant=variant,
                                                install_path=install_path,
                                                clean=clean,
                                                install=install)

        # install variant into release package repository
        if install:
            variant.install(install_path)

        return build_result.get("build_env_script")

    def _release_variant(self, variant, release_message=None, **kwargs):
        pass
        #self._print_header("Releasing %s..." % self._n_of_m(variant))


def register_plugin():
    return LocalBuildProcess
