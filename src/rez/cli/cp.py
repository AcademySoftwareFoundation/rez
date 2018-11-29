'''
Copy a package from one repository to another.
'''


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--paths", type=str,
        help="set package search path (ignores --no-local if set)")
    parser.add_argument(
        "--nl", "--no-local", dest="no_local", action="store_true",
        help="don't search local packages")
    parser.add_argument(
        "-o", "--overwrite", action="store_true",
        help="overwrite existing package/variants")
    parser.add_argument(
        "-s", "--shallow", action="store_true",
        help="perform a shallow copy (symlink directories)")
    parser.add_argument(
        "-k", "--keep-timestamp", action="store_true",
        help="keep timestamp of source package. Note that this is ignored if "
        "you're copying variant(s) into an existing package.")
    parser.add_argument(
        "-f", "--force", action="store_true",
        help="copy package even if it isn't relocatable (use at your own risk)")
    parser.add_argument(
        "--variants", nargs='+', type=int, metavar="INDEX",
        help="select variants to copy (zero-indexed).")
    pkg_action = parser.add_argument(
        "PKG",
        help="package to copy")
    parser.add_argument(
        "DST_REPO",
        help="path of repository to copy package to")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        pkg_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    import os
    import sys

    from rez.config import config
    from rez.package_copy import copy_package
    from rez.utils.formatting import PackageRequest
    from rez.packages_ import iter_packages

    # Load the source package.
    #

    if opts.paths:
        paths = opts.paths.split(os.pathsep)
        paths = [x for x in paths if x]
    elif opts.no_local:
        paths = config.nonlocal_packages_path
    else:
        paths = None

    req = PackageRequest(opts.PKG)

    it = iter_packages(
        name=req.name,
        range_=req.range_,
        paths=paths
    )

    src_pkgs = list(it)
    if not src_pkgs:
        print >> sys.stderr, "No matching packages found."
        sys.exit(1)

    if len(src_pkgs) > 1:
        print >> sys.stderr, "More than one package matches, please choose:"
        for pkg in sorted(src_pkgs, key=lambda x: x.version):
            print >> sys.stderr, pkg.qualified_name
        sys.exit(1)

    src_pkg = src_pkgs[0]

    # Perform the copy.
    #

    variants = opts.variants or None

    result = copy_package(
        package=src_pkg,
        dest_repository_path=opts.DST_REPO,
        variants=variants,
        overwrite=opts.overwrite,
        shallow=opts.shallow,
        keep_timestamp=opts.keep_timestamp,
        force=opts.force,
        verbose=opts.verbose
    )

    # Print info about the result.
    #

    copied = result["copied"]
    skipped = result["skipped"]

    # specific output for non-varianted packages
    if src_pkg.num_variants == 0:
        if copied:
            dest_pkg = copied[0][1].parent
            print("Copied %s to %s" % (src_pkg.uri, dest_pkg.uri))
        else:
            assert skipped
            dest_pkg = skipped[0][1].parent
            print(
                "Target package already exists: %s. Use 'overwrite' to replace it."
                % dest_pkg.uri
            )

    # varianted package
    else:
        if copied:
            print("%d variants were copied:" % len(copied))
            for src_variant, dest_variant in copied:
                print("  %s -> %s" % (src_variant.uri, dest_variant.uri))

        if skipped:
            print("%d variants were skipped (target exists):" % len(skipped))
            for src_variant, dest_variant in skipped:
                print("  %s !-> %s" % (src_variant.uri, dest_variant.uri))


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
