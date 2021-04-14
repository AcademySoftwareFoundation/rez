'''
Copy a package from one repository to another.
'''
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--dest-path", metavar="PATH",
        help="package repository destination path. Defaults to the same "
        "repository as the given package (this is only supported for renaming "
        "and reversioning).")
    parser.add_argument(
        "--paths", metavar="PATHS",
        help="set package search path (ignores --no-local if set)")
    parser.add_argument(
        "--nl", "--no-local", dest="no_local", action="store_true",
        help="don't search local packages")

    parser.add_argument(
        "--reversion", metavar="VERSION",
        help="copy to a different package version")
    parser.add_argument(
        "--rename", metavar="NAME",
        help="copy to a different package name")
    parser.add_argument(
        "-o", "--overwrite", action="store_true",
        help="overwrite existing package/variants")
    parser.add_argument(
        "-s", "--shallow", action="store_true",
        help="perform a shallow copy (symlinks topmost directories)")
    parser.add_argument(
        "--follow-symlinks", action="store_true",
        help="follow symlinks when copying package payload, rather than copying "
        "the symlinks themselves.")
    parser.add_argument(
        "-k", "--keep-timestamp", action="store_true",
        help="keep timestamp of source package. Note that this is ignored if "
        "you're copying variant(s) into an existing package.")
    parser.add_argument(
        "-f", "--force", action="store_true",
        help="copy package even if it isn't relocatable (use at your own risk)")
    parser.add_argument(
        "--allow-empty", action="store_true",
        help="allow package copy into empty target repository")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="dry run mode")
    parser.add_argument(
        "--variants", nargs='+', type=int, metavar="INDEX",
        help="select variants to copy (zero-indexed).")
    parser.add_argument(
        "--variant-uri", metavar="URI",
        help="copy variant with the given URI. Ignores --variants.")
    pkg_action = parser.add_argument(
        "PKG", nargs='?',
        help="package to copy")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        pkg_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    import os
    import sys

    from rez.config import config
    from rez.package_repository import package_repository_manager
    from rez.package_copy import copy_package
    from rez.utils.formatting import PackageRequest
    from rez.packages import iter_packages, get_variant_from_uri

    if opts.variant_uri:
        if opts.PKG:
            parser.error("Supply PKG or --variant-uri, not both.")
    elif not opts.PKG:
        parser.error("Expected PKG.")

    if (not opts.dest_path) and not (opts.rename or opts.reversion):
        parser.error("--dest-path must be specified unless --rename or "
                     "--reversion are used.")

    # Load the source package.
    #

    if opts.variant_uri:
        variant = get_variant_from_uri(opts.variant_uri)
        if variant is None:
            print("Unknown variant: %s" % opts.variant_uri, file=sys.stderr)
            sys.exit(1)

        src_pkg = variant.parent
        variant_indexes = [variant.index]

    else:
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
            print("No matching packages found.", file=sys.stderr)
            sys.exit(1)

        if len(src_pkgs) > 1:
            print("More than one package matches, please choose:", file=sys.stderr)
            for pkg in sorted(src_pkgs, key=lambda x: x.version):
                print(pkg.qualified_name, file=sys.stderr)
            sys.exit(1)

        src_pkg = src_pkgs[0]
        variant_indexes = opts.variants or None

    # Determine repo and perform checks.
    #
    # A common mistake may be to specify a dest package path, rather than the
    # _repo_ path. This would cause a mess, since a package would be installed
    # into a nested location within an existing package.
    #
    if opts.dest_path:
        dest_pkg_repo = package_repository_manager.get_repository(opts.dest_path)

        if (not opts.allow_empty) and dest_pkg_repo.is_empty():
            print((
                "Attempting to copy a package into an EMPTY repository. Are you "
                "sure that --dest-path is the correct path? This should not "
                "include package name and/or version."
                "\n\n"
                "If this is a valid new package repository, use the "
                "--allow-empty flag to continue."
            ), file=sys.stderr)
            sys.exit(1)
    else:
        dest_pkg_repo = src_pkg.repository

    # Perform the copy.
    #

    result = copy_package(
        package=src_pkg,
        dest_repository=dest_pkg_repo,
        dest_name=opts.rename,
        dest_version=opts.reversion,
        variants=variant_indexes,
        overwrite=opts.overwrite,
        shallow=opts.shallow,
        follow_symlinks=opts.follow_symlinks,
        keep_timestamp=opts.keep_timestamp,
        force=opts.force,
        verbose=opts.verbose,
        dry_run=opts.dry_run
    )

    # Print info about the result.
    #

    copied = result["copied"]
    skipped = result["skipped"]

    if opts.dry_run:
        # show a good indication of target variant when it doesn't get created
        path = dest_pkg_repo.get_package_payload_path(
            package_name=opts.rename or src_pkg.name,
            package_version=opts.reversion or src_pkg.version
        )

        dry_run_uri = path + "/?"
        verb = "would be"
    else:
        verb = "were"

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
            print("%d variants %s copied:" % (len(copied), verb))

            for src_variant, dest_variant in copied:
                # None possible if dry_run
                if dest_variant is None:
                    dest_uri = dry_run_uri
                else:
                    dest_uri = dest_variant.uri

                print("  %s -> %s" % (src_variant.uri, dest_uri))

        if skipped:
            print("%d variants %s skipped (target exists):" % (len(skipped), verb))
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
