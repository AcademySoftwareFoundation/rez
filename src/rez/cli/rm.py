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
        "PATH", nargs='?',
        help="the repository containing the package(s) to remove.")


def remove_package(opts, parser):
    from rez.vendor.version.requirement import VersionedObject
    from rez.package_remove import remove_package

    if opts.dry_run:
        parser.error("--dry-run is not supported with --package")

    if not opts.PATH:
        parser.error("Must specify PATH with --package")

    obj = VersionedObject(opts.package)

    if remove_package(obj.name, obj.version, opts.PATH):
        print("Package removed.")
    else:
        print("Package not found.", file=sys.stderr)
        sys.exit(1)


def remove_ignored_since(opts, parser):
    from rez.package_remove import remove_packages_ignored_since

    if opts.PATH:
        paths = [opts.PATH]
    else:
        paths = None

    num_removed = remove_packages_ignored_since(
        days=opts.ignored_since,
        paths=paths,
        dry_run=opts.dry_run,
        verbose=opts.verbose
    )

    if num_removed:
        if opts.dry_run:
            print("%d packages would be removed." % num_removed)
        else:
            print("%d packages were removed." % num_removed)
    else:
        print("No packages were removed.")


def command(opts, parser, extra_arg_groups=None):
    if opts.package:
        remove_package(opts, parser)
    elif opts.ignored_since is not None:
        remove_ignored_since(opts, parser)
    else:
        parser.error("Must specify either --package or --ignored-since")
