"""
Install a pip-compatible python package, and its dependencies, as rez packages.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--python-version", dest="py_ver", metavar="VERSION",
        help="python version (rez package) to use, default is latest. Note "
        "that the pip package(s) will be installed with a dependency on "
        "python-MAJOR.MINOR.")
    parser.add_argument(
        "-i", "--install", action="store_true",
        help="install the package")
    parser.add_argument(
        "-s", "--search", action="store_true",
        help="search for the package on PyPi")
    parser.add_argument(
        "-r", "--release", action="store_true",
        help="install as released package; if not set, package is installed "
        "locally only")
    parser.add_argument(
        "--no-deps", action="store_true", help="Do not install dependencies")
    parser.add_argument(
        "-va", "--variant", action="append",
        help="Install package as variant, may be called multiple times.")
    parser.add_argument(
        "-p", "--prefix", type=str, metavar='PATH',
        help="install to a custom package repository path.")
    parser.add_argument(
        "PACKAGE", nargs="+",
        help="package to install or archive/url to install from")


def command(opts, parser, extra_arg_groups=None):
    from rez.pip import pip_install_package, run_pip_command

    if not (opts.search or opts.install):
        parser.error("Expected one of: --install, --search")

    if opts.search:
        p = run_pip_command(["search", opts.PACKAGE])
        p.wait()
        return

    installed_variants, skipped_variants = set(), set()
    for package in opts.PACKAGE:
        installed, skipped = pip_install_package(
            package,
            python_version=opts.py_ver,
            release=opts.release,
            prefix=opts.prefix,
            no_deps=opts.no_deps,
            variants=opts.variant
        )

        installed_variants.update(installed)
        skipped_variants.update(skipped)

    # print summary
    #
    def print_variant(v):
        pkg = v.parent
        txt = "%s: %s" % (pkg.qualified_name, pkg.uri)
        if v.subpath:
            txt += " (%s)" % v.subpath
        print("  " + txt)

    print("")

    if installed_variants:
        print("%d packages were installed:" % len(installed_variants))
        for variant in installed_variants:
            print_variant(variant)
    else:
        print("NO packages were installed.")

    if skipped_variants:
        print("\n%d packages were already installed:" % len(skipped_variants))
        for variant in skipped_variants:
            print_variant(variant)

    print("")


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
