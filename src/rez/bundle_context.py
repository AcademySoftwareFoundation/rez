import os
import os.path

from rez.exceptions import ContextBundleError
from rez.utils.logging_ import print_info, print_warning
from rez.utils.yaml import save_yaml
from rez.package_copy import copy_package


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
    if quiet:
        verbose = False
    if force:
        skip_non_relocatable = False

    if os.path.exists(dest_dir):
        raise ContextBundleError("Dest dir must not exist: %s" % dest_dir)

    if not quiet:
        label = context.load_path or "context"
        print_info("Bundling %s into %s...", label, dest_dir)

    os.mkdir(dest_dir)

    _init_bundle(dest_dir)

    relocated_package_names = _copy_variants(
        context=context,
        bundle_dir=dest_dir,
        force=force,
        skip_non_relocatable=skip_non_relocatable,
        verbose=verbose
    )

    rxt_filepath = _write_retargeted_context(
        context=context,
        bundle_dir=dest_dir,
        relocated_package_names=relocated_package_names
    )

    if verbose:
        print_info("Context bundled to %s", rxt_filepath)


def _init_bundle(bundle_dir):
    # Create bundle conf file. It doesn't contain anything at time of writing,
    # but its presence on disk signifies that this is a context bundle.
    #
    bundle_filepath = os.path.join(bundle_dir, "bundle.yaml")
    save_yaml(bundle_filepath)

    # init pkg repo
    repo_path = os.path.join(bundle_dir, "packages")
    os.mkdir(repo_path)

    # Bundled repos are always memcached disabled because they're on local disk
    # (so access should be fast); but also, local repo paths written to shared
    # memcached instance could easily clash.
    #
    settings_filepath = os.path.join(bundle_dir, "packages", "settings.yaml")
    save_yaml(settings_filepath, disable_memcached=True)


def _copy_variants(context, bundle_dir, force=False, skip_non_relocatable=False,
                   verbose=False):
    relocated_package_names = []
    repo_path = os.path.join(bundle_dir, "packages")

    for variant in context.resolved_packages:
        package = variant.parent

        if skip_non_relocatable and not package.is_relocatable:
            if verbose:
                print_warning(
                    "Skipped bundling of non-relocatable package %s",
                    package.qualified_name
                )
            continue

        copy_package(
            package=package,
            dest_repository=repo_path,
            variants=[variant.index],
            force=force,
            keep_timestamp=True,
            verbose=verbose
        )

        relocated_package_names.append(package.name)

    return relocated_package_names


def _write_retargeted_context(context, bundle_dir, relocated_package_names):
    repo_path = os.path.join(bundle_dir, "packages")
    rxt_filepath = os.path.join(bundle_dir, "context.rxt")

    bundled_context = context.retargeted(
        package_paths=[repo_path],
        package_names=relocated_package_names,
        skip_missing=True
    )

    bundled_context.save(rxt_filepath)
    return rxt_filepath
