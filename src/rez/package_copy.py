import os.path
import time

from rez.exceptions import PackageCopyError
from rez.package_repository import package_repository_manager
from rez.utils.logging_ import print_info
from rez.utils.filesystem import replacing_symlink, replacing_copy, safe_makedirs


def copy_package(package, dest_repository_path, variants=None, shallow=False,
                 overwrite=False, force=False, keep_timestamp=False,
                 verbose=False, dry_run=False):
    """Copy a package from one package repository to another.

    This copies the package definition and payload.

    The result is a dict describing which package variants were and were not
    copied. For example:

        {
            "copied": [
                (`Variant`, `Variant`)
            ],
            "skipped": [
                (`Variant`, `Variant`)
            ]
        }

    Each 2-tuple in the 'copied' or 'skipped' list contains the source and
    destination variant respectively. In the 'skipped' list, the source variant
    is the variant that was NOT copied, and the dest variant is the existing
    target variant that caused the source not to be copied. Skipped variants
    will only be present when `overwrite` is False.

    Note:
        Whether or not a package can be copied is determined by its 'relocatable'
        attribute (see the `default_relocatable` config setting for more details).
        An attempt to copy a non-relocatable package will fail. You can override
        this behaviour with the `force` argument.

    Note:
        When copying individual variants that are zero-index-based, the target
        variant that is created may have a different index. This is expected and
        is not a problem. For example, if you copy a 2nd (1-indexed) variant
        into a new target package, this will become the zeroeth variant. The
        same happens when you use rez-build's --variants flag to install variants
        in a different order.

        If a package is copied into a repo where it doesn't already exist, you
        are guaranteed that the variant order will remain the same.

    Args:
        package (`Package`): Package to copy.
        dest_repository_path (str): The package repository path to copy the
            package to.
        variants (list of int): Indexes of variants to build, or all if None.
        shallow (bool): If True, symlinks of each variant's root directory are
            created, rather than the payload being copied.
        overwrite (bool): Overwrite variants if they already exist in the
            destination package. In this case, the existing payload is removed
            before the new payload is copied.
        force (bool): Copy the package regardless of its relocatable attribute.
        keep_timestamp (bool): By default, a newly copied package will get a
            new timestamp (because that's when it was added to the target repo).
            By setting this option to True, the original package's timestamp
            is kept intact.
        verbose (bool): Verbose mode.
        dry_run (bool): Dry run mode. Dest variants in the result will be None
            in this case.

    Returns:
        Dict: See comments above.
    """
    copied = []
    skipped = []

    def finalize():
        return {
            "copied": copied,
            "skipped": skipped
        }

    # check that package is relocatable
    if not force and not package.is_relocatable:
        raise PackageCopyError(
            "Cannot copy non-relocatable package: %s" % package.uri
        )

    dest_pkg_repo = package_repository_manager.get_repository(dest_repository_path)

    # cannot copy over the top of yourself
    if package.repository == dest_pkg_repo:
        raise PackageCopyError(
            "Cannot copy a package into its own repository: %s."
            % package.uri
        )

    # determine variants to potentially install
    src_variants = []
    for variant in package.iter_variants():
        if variants is None or variant.index in variants:
            src_variants.append(variant)

    if not src_variants:
        return finalize()

    # Find variants that already exist in the dest package, and remove them
    # from the copy candidates if overwriting is disabled.
    #
    new_src_variants = []

    for src_variant in src_variants:
        existing_variant = dest_pkg_repo.install_variant(
            src_variant.resource,
            dry_run=True
        )

        if existing_variant:
            if overwrite:
                if verbose:
                    print_info("Source variant %s will overwrite %s",
                               src_variant.uri, existing_variant.uri)
            else:
                if verbose:
                    print_info(
                        "Skipping source variant %s - already exists in "
                        "destination package at %s",
                        src_variant.uri, existing_variant.uri
                    )

                skipped.append((src_variant, existing_variant))
                continue

        new_src_variants.append(src_variant)

    src_variants = new_src_variants

    # Install each variant and associated payload.
    #
    for i, src_variant in enumerate(src_variants):
        if verbose:
            print_info("Copying source variant %s into repository %s...",
                       src_variant.uri, dest_repository_path)

        if dry_run:
            dest_variant = None
        else:
            # Perform pre-install steps. For eg, a "building" marker file is created
            # in the filesystem pkg repo, so that the package dir (which doesn't have
            # variants copied into it yet) is not picked up as a valid package.
            #
            dest_pkg_repo.pre_variant_install(src_variant.resource)

            # copy include modules before the first variant install
            if i == 0:
                _copy_package_include_modules(src_variant.parent, dest_pkg_repo)

            # copy the variant's payload
            _copy_variant_payload(src_variant, dest_pkg_repo, shallow=shallow)

            overrides = {}
            if not keep_timestamp:
                overrides["timestamp"] = int(time.time())

            # install the variant into the package definition
            dest_variant = dest_pkg_repo.install_variant(
                variant_resource=src_variant.resource,
                overrides=overrides
            )

        if verbose:
            print_info("Copied source variant %s to target variant %s",
                       src_variant, dest_variant)

        copied.append((src_variant, dest_variant))

    return finalize()


def _copy_variant_payload(src_variant, dest_pkg_repo, shallow=False):
        # Get payload path of source variant. For some types (eg from a "memory"
        # type repo) there may not be a root.
        #
        variant_root = getattr(src_variant, "root", None)
        if not variant_root:
            raise PackageCopyError(
                "Cannot copy source variant %s - it is a type of variant that "
                "does not have a root.", src_variant.uri
            )

        if not os.path.isdir(variant_root):
            raise PackageCopyError(
                "Cannot copy source variant %s - its root does not appear to "
                "be present on disk (%s).", src_variant.uri, variant_root
            )

        # determine variant installation path
        variant_install_path = dest_pkg_repo.get_package_payload_path(
            package_name=src_variant.name,
            package_version=src_variant.version
        )

        if src_variant.subpath:
            variant_install_path = os.path.join(variant_install_path,
                                                src_variant.subpath)

        # perform the copy/symlinking
        if shallow:
            maybe_symlink = replacing_symlink
        else:
            maybe_symlink = replacing_copy

        if src_variant.subpath:
            # symlink/copy the last install dir to the variant root
            safe_makedirs(os.path.dirname(variant_install_path))
            maybe_symlink(variant_root, variant_install_path)
        else:
            safe_makedirs(variant_install_path)

            # copy all files, and symlink/copy all dirs within the variant
            for name in os.listdir(variant_root):
                src_path = os.path.join(variant_root, name)
                dest_path = os.path.join(variant_install_path, name)

                if os.path.isdir(src_path) and not os.path.islink(src_path):
                    maybe_symlink(src_path, dest_path)
                else:
                    replacing_copy(src_path, dest_path)


def _copy_package_include_modules(src_package, dest_pkg_repo):
    pass  # TODO


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
