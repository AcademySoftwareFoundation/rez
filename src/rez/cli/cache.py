'''
Manipulate a package cache.
'''
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-a", "--add-variants", metavar="URI", nargs='+',
        help="Add variants to the cache"
    )
    parser.add_argument(
        "DIR", nargs='?',
        help="Package cache directory; will use config setting "
        "'cache_packages_path' if not provided"
    )


def add_variant(pkgcache, uri, opts):
    from rez.packages import get_variant_from_uri
    from rez.utils.logging_ import print_info
    from rez.package_cache import PackageCache

    print_info("Adding variant %r to package cache at %s:", uri, pkgcache.path)

    variant = get_variant_from_uri(uri)
    destpath, status = pkgcache.add_variant(variant)

    if status == PackageCache.VARIANT_FOUND:
        print_info("Already exists: %s", destpath)
    elif status == PackageCache.VARIANT_COPYING:
        print_info("Another process is currently copying to: %s", destpath)
    else:
        print_info("Successfully cached to: %s", destpath)


def command(opts, parser, extra_arg_groups=None):
    import sys
    from rez.config import config
    from rez.package_cache import PackageCache

    cachepath = opts.DIR or config.cache_packages_path
    if not cachepath:
        parser.error(
            "DIR must be specified, as there is no configured "
            "'cache_packages_path'"
        )

    pkgcache = PackageCache(cachepath)

    if opts.add_variants:
        for uri in opts.add_variants:
            add_variant(pkgcache, uri, opts)
    else:
        # just print variants in the cache
        entries = list(pkgcache.iter_variants())

        if sys.stdout.isatty():
            print("%d variants in cache at %s:" % (len(entries), cachepath))

        for variant, rootpath in entries:
            print("%s -> %s" % (variant.uri, rootpath))


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
