import os
import os.path

from rez.exceptions import ContextBundleError
from rez.utils.logging_ import print_info, print_warning
from rez.utils.yaml import save_yaml
from rez.package_copy import copy_package
from rez.utils.platform_ import platform_


def bundle_context(context, dest_dir, force=False, skip_non_relocatable=False,
                   quiet=False, verbose=False):
    """Bundle a context and its variants into a relocatable dir.

    This creates a copy of a context with its variants retargeted to a local
    package repository containing only the variants the context uses. The
    generated file structure looks like so:

        /dest_dir/
            /context.rxt
            /packages/
                /foo/1.1.1/package.py
                          /...(payload)...
                /bah/4.5.6/package.py
                          /...(payload)...

    Args:
        context (`ResolvedContext`): Context to bundle
        dest_dir (str): Destination directory. Must not exist.
        force (bool): If True, relocate package even if non-relocatable. Use at
            your own risk. Overrides `skip_non_relocatable`.
        skip_non_relocatable (bool): If True, leave non-relocatable packages
            unchanged. Normally this will raise a `PackageCopyError`.
        quiet (bool): Suppress all output
        verbose (bool): Verbose mode (quiet will override)
    """
    bundler = _ContextBundler(
        context=context,
        dest_dir=dest_dir,
        force=force,
        skip_non_relocatable=skip_non_relocatable,
        verbose=verbose
    )

    bundler.bundle()


class _ContextBundler(object):
    """Performs context bundling.
    """
    def __init__(self, context, dest_dir, force=False, skip_non_relocatable=False,
                 quiet=False, verbose=False):
        if quiet:
            verbose = False
        if force:
            skip_non_relocatable = False

        self.context = context
        self.dest_dir = dest_dir
        self.force = force
        self.skip_non_relocatable = skip_non_relocatable
        self.quiet = quiet
        self.verbose = verbose

        self.logs = []

        # dict with:
        # key: package name
        # value: (Variant, Variant) (src and dest variants)
        self.copied_variants = {}

    def bundle(self):
        if os.path.exists(self.dest_dir):
            raise ContextBundleError("Dest dir must not exist: %s" % self.dest_dir)

        if not self.quiet:
            label = self.context.load_path or "context"
            print_info("Bundling %s into %s...", label, self.dest_dir)

        self._init_bundle()
        relocated_package_names = self._copy_variants()
        self._write_retargeted_context(relocated_package_names)
        self._apply_lib_patching()
        self._finalize_bundle()

    @property
    def _repo_path(self):
        return os.path.join(self.dest_dir, "packages")

    def _info(self, msg, *nargs):
        self.logs.append("INFO: %s" % (msg % nargs))

    def _warning(self, msg, *nargs):
        self.logs.append("WARNING: %s" % (msg % nargs))
        print_warning(msg, *nargs)

    def _init_bundle(self):
        os.mkdir(self.dest_dir)
        os.mkdir(self._repo_path)

        # Bundled repos are always memcached disabled because they're on local disk
        # (so access should be fast); but also, local repo paths written to shared
        # memcached instance could easily clash.
        #
        settings_filepath = os.path.join(self._repo_path, "settings.yaml")
        save_yaml(settings_filepath, disable_memcached=True)

    def _finalize_bundle(self):
        bundle_metafile = os.path.join(self.dest_dir, "bundle.yaml")
        save_yaml(bundle_metafile, logs=self.logs)

    def _copy_variants(self):
        relocated_package_names = []

        for variant in self.context.resolved_packages:
            package = variant.parent

            if self.skip_non_relocatable and not package.is_relocatable:
                self._warning(
                    "Skipped bundling of non-relocatable package %s",
                    package.qualified_name
                )
                continue

            result = copy_package(
                package=package,
                dest_repository=self._repo_path,
                variants=[variant.index],
                force=self.force,
                keep_timestamp=True,
                verbose=self.verbose
            )

            assert "copied" in result
            assert len(result["copied"]) == 1
            src_variant, dest_variant = result["copied"][0]

            self.copied_variants[package.name] = (src_variant, dest_variant)
            self._info("Copied %s into %s", src_variant, dest_variant)

            relocated_package_names.append(package.name)

        return relocated_package_names

    def _write_retargeted_context(self, relocated_package_names):
        rxt_filepath = os.path.join(self.dest_dir, "context.rxt")

        bundled_context = self.context.retargeted(
            package_paths=[self._repo_path],
            package_names=relocated_package_names,
            skip_missing=True
        )

        bundled_context.save(rxt_filepath)

        if self.verbose:
            print_info("Bundled context written to to %s", rxt_filepath)

    def _apply_lib_patching(self):
        # TODO
        if platform_.name in ("osx", "windows"):
            return

        self._apply_lib_patching_linux()

    def _apply_lib_patching_linux(self):
        """Fix elfs that reference elfs outside of the bundle.

        Finds elf files, inspects their runpath/rpath, then looks to see if
        those paths map to package also inside the bundle. If they do, they
        are removed from the lib's rpath, and the remapped path is appended
        to LD_LIBRARY_PATH instead (this occurs via the 'post_commands.py' file
        in the bundle).
        """
