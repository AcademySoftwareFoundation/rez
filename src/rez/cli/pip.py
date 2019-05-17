"""
Install a pip-compatible python package, and its dependencies, as rez packages.
"""
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--pip-version", dest="pip_ver", metavar="VERSION",
        help="pip version (rez package) to use, default is latest")
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
        help="search for the package on PyPi"),
    parser.add_argument(
        "-l", "--list", action="store_true",
        help="list available versions of a package based on PyPi"),
    parser.add_argument(
        "-q", "--query",
        help="query python pre-requisites of a specific package version on PyPi"),
    parser.add_argument(
        "-c", "--constrain",
        help="find compatible package versions based on Python version constraint before installing"),
    parser.add_argument(
        "-r", "--release", action="store_true",
        help="install as released package; if not set, package is installed "
        "locally only")
    parser.add_argument(
        "PACKAGE",
        help="package to install or archive/url to install from")


def command(opts, parser, extra_arg_groups=None):
    from rez.pip import pip_install_package, run_pip_command
    from rez.vendor.version.version import Version, VersionRange
    import sys
    import json
    import urllib2
    import itertools

    if not (opts.search or opts.install or opts.list or opts.query or opts.constrain):
        parser.error("Expected one of: --install, --search, --list, --query, --constrain")

    if opts.search:
        p = run_pip_command(["search", opts.PACKAGE])
        p.wait()
        return

    if opts.list:
        opts.PACKAGE += "=="
        output = run_pip_command(["install", opts.PACKAGE], process_output=True)
        for package_version in output:
            print(package_version)
        return

    if opts.query:
        URL = "https://pypi.python.org/pypi/{0}/{1}/json"
        try:
            data = json.load(urllib2.urlopen(URL.format(opts.PACKAGE, opts.query)))

            classifiers = data["info"]["classifiers"]
            python_requires = [classifier for classifier in classifiers if "Programming Language :: Python ::" in classifier]
            python_requires = ''.join(python_requires)
            python_requires = python_requires.split("Programming Language :: Python :: ")
            python_requires = filter(None, python_requires)

            if not python_requires:
                print("Package version is valid but PyPi does not contain a specific Python version. Too old?")
                return

            for i, j in itertools.groupby(python_requires, key=lambda x: x[0]):
                print("Python" + i + ":", [Version(z) for z in list(j) if z != i])
        except urllib2.HTTPError:
            print("Package version not found, please check rez-pip -l {0}".format(opts.PACKAGE))
        return

    option = ""
    if opts.constrain:
        ver_range = VersionRange(opts.constrain)

        URL = "https://pypi.python.org/pypi/{0}/json"
        try:
            data = json.load(urllib2.urlopen(URL.format(opts.PACKAGE)))
            releases = data["releases"].keys()
            releases = sorted(releases)

            python_reqs = {}
            valid = []
            suitable = []

            for release in releases:
                for release_info in data["releases"][release]:
                    python_version = release_info["python_version"]
                    requires_python = release_info["requires_python"]

                    if python_version == "source":
                        continue
                    elif python_version == "py2.py3":
                        suitable.append(release)
                        break
                    elif python_version == "py3":
                        if requires_python:
                            package_range = VersionRange(requires_python)
                            inrange = ver_range.intersects(package_range)
                            if inrange:
                                valid.append(release)
                                break
                        else:
                            python_reqs.setdefault(release, set()).add(Version("3"))
                    elif python_version.startswith("cp"):
                        ver = filter(str.isdigit, str(python_version))
                        raw_ver = ver[:1] + "." + ver[-1]
                        python_reqs.setdefault(release, set()).add(Version(raw_ver))
                    else:
                        python_reqs.setdefault(release, set()).add(Version(python_version))

            for k, v in python_reqs.items():
                for item in python_reqs[k]:
                    if ver_range.contains_version(item):
                        if k not in valid:
                            valid.append(k)
                            break
            print("The following versions of {0} are compatible with Python {1}".format(opts.PACKAGE, opts.constrain))
            if not valid:
                print("\tNo package version specifies compatibility with Python version {0}".format(opts.constrain))
            else:
                for package_version in sorted(valid):
                    print("\t" + package_version)

            if suitable:
                print("")
                print("")

                print("The following versions of {0} are compatible with all Python versions (unversioned)".format(opts.PACKAGE))
                for package_version in sorted(suitable):
                    print("\t" + package_version)

            if valid or suitable:
                while option != "q" or option not in valid:
                    option = raw_input("Install version (q to quit): ")

                    if option == "q":
                        return
                    elif option in valid:
                        break
                    else:
                        continue
            else:
                return

        except urllib2.HTTPError:
            print("Package version not found, please check rez-pip -l {0}".format(opts.PACKAGE))

    if option:
        opts.PACKAGE += "=={0}".format(option)

    installed_variants, skipped_variants, variant_types = pip_install_package(
        opts.PACKAGE,
        pip_version=opts.pip_ver,
        python_version=opts.py_ver,
        release=opts.release)

    # print summary
    #

    def print_variant(v):
        pkg = v.parent
        txt = "%s: %s" % (pkg.qualified_name, pkg.uri)
        if v.subpath:
            txt += " (%s)" % v.subpath
        print("  " + txt)

    print()
    if installed_variants:
        print "%d packages were installed:" % len(installed_variants)
        for variant, purity in zip(installed_variants, variant_types):
            print("[{}]".format(purity))
            print_variant(variant)
    else:
        print("NO packages were installed.")

    if skipped_variants:
        print()
        print("%d packages were already installed:" % len(skipped_variants))
        for variant in skipped_variants:
            print_variant(variant)

    print()


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
