'''
Manipulate a package cache.
'''
from __future__ import print_function
from argparse import SUPPRESS
import sys


def setup_parser(parser, completions=False):
    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "-a", "--add-variants", metavar="URI", nargs='+',
        help="Add variants to the cache"
    )
    group.add_argument(
        "-r", "--remove-variants", metavar="URI", nargs='+',
        help="Remove variants from cache"
    )
    group.add_argument(
        "--daemon", action="store_true", help=SUPPRESS
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


def command(opts, parser, extra_arg_groups=None):
    import sys
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

    else:
        # just print current state of package cache
        def _sort(entry):
            variant, _, status = entry
            return (statuses[status][-1], variant.name)

        entries = sorted(pkgcache.get_variants(), key=_sort)

        if not entries:
            print("No cached packages.", file=sys.stderr)
            sys.exit(0)

        rows = [
            ["status", "package", "variant uri", "cached root path", colorize.heading],
            ["------", "-------", "-----------", "----------------", colorize.heading]
        ]

        for variant, rootpath, status in entries:
            label, color, _ = statuses[status]

            rows.append([
                label,
                variant.parent.qualified_name,
                variant.uri,
                rootpath or '-',
                color
            ])

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
