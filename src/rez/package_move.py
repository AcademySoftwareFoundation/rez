from rez.exceptions import PackageMoveError
from rez.package_copy import copy_package
from rez.package_repository import package_repository_manager
from rez.utils.logging_ import print_info
from rez.vendor.six import six


basestring = six.string_types[0]


def move_package(package, dest_repository, keep_timestamp=False, force=False,
                 verbose=False):
    """Move a package.

    Moving a package means copying the package to a destination repo, and
    ignoring (ie hiding - not removing) the source package. The package must
    not already exist in the destination repo.

    Args:
        package (`Package`): Package to move.
        dest_repository (`PackageRepository` or str): The package repository, or
            a package repository path, to move the package into.
        keep_timestamp (bool): By default, a newly copied package will get a
            new timestamp (because that's when it was added to the target repo).
            By setting this option to True, the original package's timestamp
            is kept intact.
        force (bool): Move the package regardless of its relocatable attribute.
            Use at your own risk (there is no guarantee the resulting package
            will be functional).
        verbose (bool): Verbose mode.

    Returns:
        `Package`: The newly created package in the destination repo.
    """
    def _info(msg, *nargs):
        if verbose:
            print_info(msg, *nargs)

    # get dest repo
    if isinstance(dest_repository, basestring):
        repo_path = dest_repository
        dest_pkg_repo = package_repository_manager.get_repository(repo_path)
    else:
        dest_pkg_repo = dest_repository

    # check that the package doesn't already exist in the dest repo
    pkg = dest_pkg_repo.get_package(package.name, package.version)
    if pkg:
        raise PackageMoveError(
            "Package already exists at destination: %s"
            % pkg.uri
        )

    # move the pkg as atomically as possible:
    #
    # 1. Hide the dest package (even tho it doesn't exist yet)
    # 2. Copy the package
    # 3. Unhide the dest package
    # 4. Hide the src package
    #

    # 1.
    dest_pkg_repo.ignore_package(
        package.name, package.version, allow_missing=True)
    _info("Ignored %s in %s ahead of time", package.qualified_name, dest_pkg_repo)

    try:
        # 2.
        result = copy_package(
            package=package,
            dest_repository=dest_pkg_repo,
            force=force,
            keep_timestamp=keep_timestamp,
            verbose=verbose
        )
    finally:
        # 3.
        dest_pkg_repo.unignore_package(package.name, package.version)
        _info("Unignored %s in %s", package.qualified_name, dest_pkg_repo)

    # 4.
    package.repository.ignore_package(package.name, package.version)
    _info("Ignored %s", package.uri)

    # finish up
    a_dest_variant = result["copied"][0][1]
    dest_pkg = a_dest_variant.parent

    _info("Package %s moved to %s", package.uri, dest_pkg.uri)
    return dest_pkg
