from rez.package_repository import package_repository_manager
from rez.utils.logging_ import print_info
from rez.config import config


def remove_package(package_name, package_version, path):
    """Remove a package from its repository.

    Note that you are able to remove a package that is hidden (ie ignored).
    This is why a Package instance is not specified (if the package were hidden,
    you wouldn't be able to get one).

    Args:
        package_name (str): Name of package.
        package_version (`Version`): Package version.
        path (str): Package repository path containing the package.

    Returns:
        bool: True if the package was removed, False if package not found.
    """
    repo = package_repository_manager.get_repository(path)
    return repo.remove_package(package_name, package_version)


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
