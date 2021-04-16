from rez.package_repository import package_repository_manager
from rez.vendor.version.version import Version
from rez.utils.logging_ import print_info
from rez.vendor.six import six
from rez.config import config


basestring = six.string_types[0]


def remove_package(name, version, path):
    """Remove a package from its repository.

    Note that you are able to remove a package that is hidden (ie ignored).
    This is why a Package instance is not specified (if the package were hidden,
    you wouldn't be able to get one).

    Args:
        name (str): Name of package.
        version (Version or str): Version of the package, eg '1.0.0'
        path (str): Package repository path containing the package.

    Returns:
        bool: True if the package was removed, False if package not found.
    """
    if isinstance(version, basestring):
        version = Version(version)

    repo = package_repository_manager.get_repository(path)
    return repo.remove_package(name, version)


def remove_packages_ignored_since(days, paths=None, dry_run=False, verbose=False):
    """Remove packages ignored for >= specified number of days.

    Args:
        days (int): Remove packages ignored >= this many days
        paths (list of str, optional): Paths to search for packages, defaults
            to `config.packages_path`.
        dry_run: Dry run mode
        verbose (bool): Verbose mode

    Returns:
        int: Number of packages removed. In dry-run mode, returns the number of
        packages that _would_ be removed.
    """
    num_removed = 0

    for path in (paths or config.packages_path):
        repo = package_repository_manager.get_repository(path)

        if verbose:
            print_info("Searching %s...", repo)

        num_removed += repo.remove_ignored_since(
            days=days,
            dry_run=dry_run,
            verbose=verbose
        )

    return num_removed
