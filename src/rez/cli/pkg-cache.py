'''
Manipulate a package cache.
'''
from __future__ import print_function
from argparse import SUPPRESS
import os.path
import sys


def setup_parser(parser, completions=False):
    column_choices = (
        "status",
        "package",
        "variant_uri",
        "orig_path",
        "cache_path"
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "-a", "--add-variants", metavar="URI", nargs='+',
        help="Add variants to the cache"
    )
    group.add_argument(
        "--logs", action="store_true",
        help="View logs"
    )
    group.add_argument(
        "-r", "--remove-variants", metavar="URI", nargs='+',
        help="Remove variants from cache"
    )
    group.add_argument(
        "--clean", action="store_true",
        help="Remove unused variants and other cache files pending deletion"
    )
    # run as a daemon that adds pending variants to the cache, then exits
    group.add_argument(
        "--daemon", action="store_true", help=SUPPRESS
    )
    parser.add_argument(
        "-c", "--columns", nargs='+', choices=column_choices,
        default=["status", "package", "variant_uri", "cache_path"],
        help="Columns to print, choose from: %s" % ", ".join(column_choices)
    )
    parser.add_argument(
        "-f", "--force", action="store_true",
        help="Force a package add, even if package is not cachable. Only "
        "applicable with --add"
    )
    parser.add_argument(
        "DIR", nargs='?',
        help="Package cache directory; will use config setting "
        "'cache_packages_path' if not provided"
    )


def add_variant(pkgcache, uri, opts):
    from rez.packages import get_variant_from_uri
    from rez.utils.logging_ import print_info, print_warning
    from rez.package_cache import PackageCache

    print_info("Adding variant %r to package cache at %s:", uri, pkgcache.path)

    variant = get_variant_from_uri(uri)
    if variant is None:
        print("No such variant: %s" % uri, file=sys.stderr)
        sys.exit(1)

    destpath, status = pkgcache.add_variant(variant, force=opts.force)

    if status == PackageCache.VARIANT_FOUND:
        print_info("Already exists: %s", destpath)
    elif status == PackageCache.VARIANT_COPYING:
        print_warning("Another process is currently copying to: %s", destpath)
    else:
        print_info("Successfully cached to: %s", destpath)


def remove_variant(pkgcache, uri, opts):
    from rez.packages import get_variant_from_uri
    from rez.utils.logging_ import print_info, print_warning, print_error
    from rez.package_cache import PackageCache

    print_info("Removing variant %r from package cache at %s:", uri, pkgcache.path)

    variant = get_variant_from_uri(uri)
    if variant is None:
        print("No such variant: %s" % uri, file=sys.stderr)
        sys.exit(1)

    status = pkgcache.remove_variant(variant)

    if status == PackageCache.VARIANT_NOT_FOUND:
        print_error("No such variant found in cache")
    elif status == PackageCache.VARIANT_COPYING:
        print_warning("Another process is currently caching this variant")
    else:
        print_info("Variant successfully removed")


def view_logs(pkgcache, opts):
    from rez.utils.logging_ import view_file_logs

    view_file_logs(
        os.path.join(pkgcache._log_dir, "*.log"),
        loglevel_index=4
    )


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.package_cache import PackageCache
    from rez.utils.formatting import print_colored_columns
    from rez.utils import colorize

    statuses = {
        PackageCache.VARIANT_FOUND: ("cached", colorize.local, 0),
        PackageCache.VARIANT_COPYING: ("copying", colorize.warning, 1),
        PackageCache.VARIANT_COPY_STALLED: ("stalled", colorize.error, 2),
        PackageCache.VARIANT_PENDING: ("pending", colorize.inactive, 3)
    }

    cachepath = opts.DIR or config.cache_packages_path
    if not cachepath:
        parser.error(
            "DIR must be specified, as there is no configured "
            "'cache_packages_path'"
        )

    pkgcache = PackageCache(cachepath)

    if opts.daemon:
        pkgcache.run_daemon()

    elif opts.add_variants:
        for uri in opts.add_variants:
            add_variant(pkgcache, uri, opts)

    elif opts.remove_variants:
        for uri in opts.remove_variants:
            remove_variant(pkgcache, uri, opts)

    elif opts.clean:
        pkgcache.clean()

    elif opts.logs:
        view_logs(pkgcache, opts)

    else:
        tty = sys.stdout.isatty()

        # just print current state of package cache
        if tty:
            print("Package cache at %s:\n" % cachepath)

        def _sort(entry):
            variant, _, status = entry
            return (statuses[status][-1], variant.name)

        entries = sorted(pkgcache.get_variants(), key=_sort)

        if not entries:
            print("No cached packages.", file=sys.stderr)
            sys.exit(0)

        rows = []

        if tty:
            rows.append([c.replace('_', ' ') for c in opts.columns] + [None])  # headers
            rows.append([('-' * len(c)) for c in opts.columns] + [None])  # underlines

        for variant, rootpath, status in entries:
            status_str, color, _ = statuses[status]
            row = []

            for c in opts.columns:
                if c == "status":
                    row.append(status_str)
                elif c == "package":
                    row.append(variant.parent.qualified_name)
                elif c == "variant_uri":
                    row.append(variant.uri)
                elif c == "orig_path":
                    row.append(variant.root)
                else:  # cached_path
                    row.append(rootpath or '-')

            row.append(color)
            rows.append(row)

        pr = colorize.Printer()
        print_colored_columns(pr, rows)


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
