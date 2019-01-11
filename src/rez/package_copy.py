from functools import partial
import os.path
import time

from rez.config import config
from rez.exceptions import PackageCopyError
from rez.package_repository import package_repository_manager
from rez.serialise import FileFormat
from rez.utils.sourcecode import IncludeModuleManager
from rez.utils.logging_ import print_info
from rez.utils.filesystem import replacing_symlink, replacing_copy, \
    safe_makedirs, additive_copytree


def copy_package(package, dest_repository, variants=None, shallow=False,
                 dest_name=None, dest_version=None, overwrite=False, force=False,
                 follow_symlinks=False, dry_run=False, keep_timestamp=False,
                 skip_payload=False, overrides=None, verbose=False):
    """Copy a package from one package repository to another.

    This copies the package definition and payload. The package can also be
    re-named and/or re-versioned using the `dest_name` and `dest_version` args.

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

    Args:
        package (`Package`): Package to copy.
        dest_repository (`PackageRepository` or str): The package repository, or
            a package repository path, to copy the package into.
        variants (list of int): Indexes of variants to build, or all if None.
        shallow (bool): If True, symlinks of each variant's root directory are
            created, rather than the payload being copied.
        dest_name (str): If provided, copy the package to a new package name.
        dest_version (str or `Version`): If provided, copy the package to a new
            version.
        overwrite (bool): Overwrite variants if they already exist in the
            destination package. In this case, the existing payload is removed
            before the new payload is copied.
        force (bool): Copy the package regardless of its relocatable attribute.
            Use at your own risk (there is no guarantee the resulting package
            will be functional).
        follow_symlinks (bool): Follow symlinks when copying package payload,
            rather than copying the symlinks themselves.
        keep_timestamp (bool): By default, a newly copied package will get a
            new timestamp (because that's when it was added to the target repo).
            By setting this option to True, the original package's timestamp
            is kept intact. Note that this will have no effect if variant(s)
            are copied into an existing package.
        skip_payload (bool): If True, do not copy the package payload.
        overrides (dict): See `PackageRepository.install_variant`.
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
    if not force and not skip_payload and not package.is_relocatable:
        raise PackageCopyError(
            "Cannot copy non-relocatable package: %s" % package.uri
        )

    if isinstance(dest_repository, basestring):
        repo_path = dest_repository
        dest_pkg_repo = package_repository_manager.get_repository(repo_path)
    else:
        dest_pkg_repo = dest_repository

    # cannot copy package over the top of itself
    if package.repository == dest_pkg_repo and \
            (dest_name is None or dest_name == package.name) and \
            (dest_version is None or str(dest_version) == str(package.version)):
        raise PackageCopyError(
            "Cannot copy package over itself: %s." % package.uri
        )

    # determine variants to potentially install
    src_variants = []
    for variant in package.iter_variants():
        if variants is None or variant.index in variants:
            src_variants.append(variant)

    if not src_variants:
        return finalize()

    # Construct overrides.
    #
    overrides = (overrides or {}).copy()

    if dest_name:
        overrides["name"] = dest_name
    if dest_version:
        overrides["version"] = dest_version

    # Find variants that already exist in the dest package, and remove them
    # from the copy candidates if overwriting is disabled.
    #
    new_src_variants = []

    for src_variant in src_variants:
        existing_variant = dest_pkg_repo.install_variant(
            src_variant.resource,
            overrides=overrides,
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
                       src_variant.uri, str(dest_pkg_repo))

        if dry_run:
            dest_variant = None
        else:
            if not skip_payload:
                # Perform pre-install steps. For eg, a "building" marker file is
                # created in the filesystem pkg repo, so that the package dir
                # (which doesn't have variants copied into it yet) is not picked
                # up as a valid package.
                #
                dest_pkg_repo.pre_variant_install(src_variant.resource)

                # copy include modules before the first variant install
                if i == 0:
                    _copy_package_include_modules(
                        src_variant.parent,
                        dest_pkg_repo,
                        overrides=overrides
                    )

                # copy the variant's payload
                _copy_variant_payload(
                    src_variant=src_variant,
                    dest_pkg_repo=dest_pkg_repo,
                    shallow=shallow,
                    follow_symlinks=follow_symlinks,
                    overrides=overrides
                )

            # construct overrides
            overrides_ = overrides.copy()

            if not keep_timestamp:
                overrides_["timestamp"] = int(time.time())

            # install the variant into the package definition
            dest_variant = dest_pkg_repo.install_variant(
                variant_resource=src_variant.resource,
                overrides=overrides_
            )

        if verbose:
            print_info("Copied source variant %s to target variant %s",
                       src_variant, dest_variant)

        copied.append((src_variant, dest_variant))

    return finalize()


def _copy_variant_payload(src_variant, dest_pkg_repo, shallow=False,
                          follow_symlinks=False, overrides=None):
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

        dest_variant_name = overrides.get("name") or src_variant.name
        dest_variant_version = overrides.get("version") or src_variant.version

        # determine variant installation path
        variant_install_path = dest_pkg_repo.get_package_payload_path(
            package_name=dest_variant_name,
            package_version=dest_variant_version
        )

        if src_variant.subpath:
            variant_install_path = os.path.join(variant_install_path,
                                                src_variant.subpath)

        # perform the copy/symlinking
        copy_func = partial(replacing_copy,
                            follow_symlinks=follow_symlinks)

        if shallow:
            maybe_symlink = replacing_symlink
        else:
            maybe_symlink = copy_func

        if src_variant.subpath:
            # symlink/copy the last install dir to the variant root
            safe_makedirs(os.path.dirname(variant_install_path))
            maybe_symlink(variant_root, variant_install_path)
        else:
            safe_makedirs(variant_install_path)

            # Symlink/copy all files and dirs within the null variant, except
            # for the package definition itself.
            #
            for name in os.listdir(variant_root):
                is_pkg_defn = False

                # skip package definition file
                name_ = os.path.splitext(name)[0]
                if name_ in config.plugins.package_repository.filesystem.package_filenames:
                    for fmt in (FileFormat.py, FileFormat.yaml):
                        filename = name_ + '.' + fmt.extension
                        if name == filename:
                            is_pkg_defn = True
                            break

                if is_pkg_defn:
                    continue

                src_path = os.path.join(variant_root, name)
                dest_path = os.path.join(variant_install_path, name)

                if os.path.islink(src_path):
                    copy_func(src_path, dest_path)
                else:
                    maybe_symlink(src_path, dest_path)


def _copy_package_include_modules(src_package, dest_pkg_repo, overrides=None):
    src_include_modules_path = \
        os.path.join(src_package.base, IncludeModuleManager.include_modules_subpath)

    if not os.path.exists(src_include_modules_path):
        return

    dest_package_name = overrides.get("name") or src_package.name
    dest_package_version = overrides.get("version") or src_package.version

    pkg_install_path = dest_pkg_repo.get_package_payload_path(
        package_name=dest_package_name,
        package_version=dest_package_version
    )

    dest_include_modules_path = \
        os.path.join(pkg_install_path, IncludeModuleManager.include_modules_subpath)

    safe_makedirs(dest_include_modules_path)
    additive_copytree(src_include_modules_path, dest_include_modules_path)


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
