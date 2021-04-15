'''
Remove package(s) from a repository.
'''
from __future__ import print_function
import sys


def setup_parser(parser, completions=False):
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-p", "--package",
        help="remove the specified package (eg 'foo-1.2.3'). This will work "
        "even if the package is currently ignored.")
    group.add_argument(
        "-i", "--ignored-since", type=int, metavar="DAYS",
        help="remove all packages that have been ignored for >= DAYS")

    parser.add_argument(
        "--dry-run", action="store_true",
        help="dry run mode")
    parser.add_argument(
        "PATH",
        help="the repository containing the package(s) to remove.")


def remove_package(repo, opts, parser):
    from rez.vendor.version.requirement import VersionedObject

    if opts.dry_run:
        parser.error("--dry-run is not supported with --package")

    obj = VersionedObject(opts.package)

    if repo.remove_package(obj.name, obj.version):
        print("Package removed.")
    else:
        print("Package not found.", file=sys.stderr)
        sys.exit(1)


def remove_ignored_since(repo, opts, parser):
    count = repo.remove_ignored_since(
        days=opts.ignored_since,
        dry_run=opts.dry_run,
        verbose=opts.verbose
    )

    if count:
        print("%d packages were removed." % count)
    else:
        print("No packages were removed.")


def command(opts, parser, extra_arg_groups=None):
    from rez.package_repository import package_repository_manager

    repo = package_repository_manager.get_repository(opts.PATH)

    if opts.package:
        remove_package(repo, opts, parser)
    elif opts.ignored_since:
        remove_ignored_since(repo, opts, parser)
    else:
        parser.error("Must specify either --package or --ignored-since")
