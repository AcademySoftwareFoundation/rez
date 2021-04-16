'''
Move a package from one repository to another.
'''
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-d", "--dest-path", metavar="PATH", required=True,
        help="package repository to move PKG to.")
    parser.add_argument(
        "-k", "--keep-timestamp", action="store_true",
        help="keep timestamp of source package.")
    parser.add_argument(
        "-f", "--force", action="store_true",
        help="move package even if it isn't relocatable (use at your own risk)")
    pkg_action = parser.add_argument(
        "PKG",
        help="package to move (eg 'foo-1.2.3')")
    parser.add_argument(
        "PATH", nargs='?',
        help="The repository containing the package. If not specified, this "
        "command will present you with a list to select from.")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        pkg_action.completer = PackageCompleter


def list_repos_containing_pkg(pkg_name, pkg_version):
    from rez.config import config
    from rez.package_repository import package_repository_manager
    import sys

    # search for package in each searchpath
    matching_repos = []

    for path in config.packages_path:
        repo = package_repository_manager.get_repository(path)
        if repo.get_package(pkg_name, pkg_version):
            matching_repos.append(repo)

    if matching_repos:
        print("No action taken. Run again, and set PATH to one of:")
        for repo in matching_repos:
            print(str(repo))
    else:
        print("Package not found.", file=sys.stderr)
        sys.exit(1)


def command(opts, parser, extra_arg_groups=None):
    from rez.vendor.version.requirement import VersionedObject
    from rez.packages import get_package_from_repository
    from rez.package_move import move_package
    import sys

    obj = VersionedObject(opts.PKG)

    if opts.PATH is None:
        list_repos_containing_pkg(obj.name, obj.version)
        sys.exit(0)

    # find src pkg
    src_pkg = get_package_from_repository(obj.name, obj.version, opts.PATH)

    if src_pkg is None:
        print("Package not found.", file=sys.stderr)
        sys.exit(1)

    move_package(
        package=src_pkg,
        dest_repository=opts.dest_path,
        keep_timestamp=opts.keep_timestamp,
        force=opts.force,
        verbose=opts.verbose
    )
