from functools import partial
import os.path
import shutil
import time

from rez.config import config
from rez.exceptions import PackageCopyError
from rez.package_repository import package_repository_manager
from rez.packages import Variant
from rez.serialise import FileFormat
from rez.utils import with_noop
from rez.utils.base26 import create_unique_base26_symlink
from rez.utils.sourcecode import IncludeModuleManager
from rez.utils.logging_ import print_info, print_warning
from rez.utils.filesystem import replacing_symlink, replacing_copy, \
    safe_makedirs, additive_copytree, make_path_writable, get_existing_path
from rez.vendor.six import six


basestring = six.string_types[0]


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
        existing_variant_resource = dest_pkg_repo.install_variant(
            src_variant.resource,
            overrides=overrides,
            dry_run=True
        )

        if existing_variant_resource:
            existing_variant = Variant(existing_variant_resource)

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
                    overrides=overrides,
                    verbose=verbose
                )

            # construct overrides
            overrides_ = overrides.copy()

            if not keep_timestamp and "timestamp" not in overrides:
                overrides_["timestamp"] = int(time.time())

            # install the variant into the package definition
            dest_variant_resource = dest_pkg_repo.install_variant(
                variant_resource=src_variant.resource,
                overrides=overrides_
            )

            dest_variant = Variant(dest_variant_resource)

        if verbose:
            print_info("Copied source variant %s to target variant %s",
                       src_variant.uri, dest_variant.uri)

        copied.append((src_variant, dest_variant))

    return finalize()


def _copy_variant_payload(src_variant, dest_pkg_repo, shallow=False,
                          follow_symlinks=False, overrides=None, verbose=False):
    # Get payload path of source variant. For some types (eg from a "memory"
    # type repo) there may not be a root.
    #
    variant_root = getattr(src_variant, "root", None)

    if not variant_root:
        raise PackageCopyError(
            "Cannot copy source variant %s - it is a type of variant that "
            "does not have a root." % src_variant.uri
        )

    if not os.path.isdir(variant_root):
        raise PackageCopyError(
            "Cannot copy source variant %s - its root does not appear to "
            "be present on disk (%s)." % src_variant.uri, variant_root
        )

    dest_variant_name = overrides.get("name") or src_variant.name
    dest_variant_version = overrides.get("version") or src_variant.version

    # determine variant installation path
    dest_pkg_payload_path = dest_pkg_repo.get_package_payload_path(
        package_name=dest_variant_name,
        package_version=dest_variant_version
    )

    is_varianted = (src_variant.index is not None)
    src_variant_subpath = None

    if is_varianted:
        src_variant_subpath = src_variant._non_shortlinked_subpath

        variant_install_path = os.path.join(
            dest_pkg_payload_path, src_variant_subpath)
    else:
        variant_install_path = dest_pkg_payload_path

    # get ready for copy/symlinking
    copy_func = partial(replacing_copy,
                        follow_symlinks=follow_symlinks)

    if shallow:
        maybe_symlink = replacing_symlink
    else:
        maybe_symlink = copy_func

    # possibly make install path temporarily writable
    last_dir = get_existing_path(
        variant_install_path,
        topmost_path=os.path.dirname(dest_pkg_payload_path))

    if last_dir and config.make_package_temporarily_writable:
        ctxt = make_path_writable(last_dir)
    else:
        ctxt = with_noop()

    # copy the variant payload
    with ctxt:
        safe_makedirs(variant_install_path)

        # determine files not to copy
        skip_files = []

        if is_varianted and not src_variant.parent.hashed_variants:
            # Detect overlapped variants. This is the case where one variant subpath
            # might be A, and another is A/B. We must ensure that A/B is not created
            # as a symlink during shallow install of variant A - that would then
            # cause A/B payload to be installed back into original package, possibly
            # corrupting it.
            #
            # Here we detect this case, and create a list of dirs not to copy/link,
            # because they are in fact a subpath dir for another variant.
            #
            # Note that for hashed variants, we don't do this check because overlapped
            # variants are not possible.
            #
            skip_files.extend(_get_overlapped_variant_dirs(src_variant))
        else:
            # just skip package definition file
            for name in config.plugins.package_repository.filesystem.package_filenames:
                for fmt in (FileFormat.py, FileFormat.yaml):
                    filename = name + '.' + fmt.extension
                    skip_files.append(filename)

        # copy/link all topmost files within the variant root
        for name in os.listdir(variant_root):
            if name in skip_files:
                filepath = os.path.join(variant_root, name)

                if verbose and is_varianted:
                    print_info(
                        "Did not copy %s - this is part of an overlapping "
                        "variant's root path.", filepath
                    )

                continue

            src_path = os.path.join(variant_root, name)
            dest_path = os.path.join(variant_install_path, name)

            if os.path.islink(src_path):
                copy_func(src_path, dest_path)
            else:
                maybe_symlink(src_path, dest_path)

    # copy permissions of source variant dirs onto dest
    src_package = src_variant.parent
    src_pkg_repo = src_package.repository

    src_pkg_payload_path = src_pkg_repo.get_package_payload_path(
        package_name=src_package.name,
        package_version=src_package.version
    )

    shutil.copystat(src_pkg_payload_path, dest_pkg_payload_path)

    subpath = src_variant_subpath

    while subpath:
        src_path = os.path.join(src_pkg_payload_path, subpath)
        dest_path = os.path.join(dest_pkg_payload_path, subpath)
        shutil.copystat(src_path, dest_path)
        subpath = os.path.dirname(subpath)

    # create the variant shortlink
    if src_variant.parent.hashed_variants:
        try:
            # base _v dir
            base_shortlinks_path = os.path.join(
                dest_pkg_payload_path,
                src_package.config.variant_shortlinks_dirname
            )

            safe_makedirs(base_shortlinks_path)

            # shortlink
            rel_variant_path = os.path.relpath(
                variant_install_path, base_shortlinks_path)
            create_unique_base26_symlink(
                base_shortlinks_path, rel_variant_path)

        except Exception as e:
            # Treat any error as warning - lack of shortlink is not
            # a breaking issue, it just means the variant root path
            # will be long.
            #
            print_warning(
                "Error creating variant shortlink for %s: %s: %s",
                variant_install_path, e.__class__.__name__, e
            )


def _get_overlapped_variant_dirs(src_variant):
    package = src_variant.parent
    dirs = set()

    # find other variants that overlap src_variant and have deeper subpath
    for variant in package.iter_variants():
        if variant.index == src_variant.index:
            continue

        if variant.root.startswith(src_variant.root + os.path.sep):
            relpath = os.path.relpath(variant.root, src_variant.root)
            topmost_dir = relpath.split(os.path.sep)[0]
            dirs.add(topmost_dir)

    return list(dirs)


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

    last_dir = get_existing_path(dest_include_modules_path,
                                 topmost_path=os.path.dirname(pkg_install_path))

    if last_dir:
        ctxt = make_path_writable(last_dir)
    else:
        ctxt = with_noop()

    with ctxt:
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
