"""
Install a pip-compatible python package, and its dependencies, as rez packages.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--pip-version", dest="pip_ver", metavar="VERSION",
        help="pip version (rez package) to use, default is latest")
    parser.add_argument(
        "--python-version", dest="py_ver", metavar="VERSION",
        help="python version (rez package) to use, default is latest. Note "
        "that the pip package(s) will be installed with a dependency on "
        "python-MAJOR.MINOR. You can also provide a comma-separated list to "
        "install for multiple pythons at once, eg '2.6,2.7'")
    parser.add_argument(
        "PACKAGE",
        help="package to install or archive/url to install from")


def command(opts, parser, extra_arg_groups=None):
    from rez.pip import pip_install_package

    if opts.py_ver:
        py_vers = opts.py_ver.strip(',').split(',')
    else:
        py_vers = None

    pip_install_package(opts.PACKAGE,
                        pip_version=opts.pip_ver,
                        python_versions=py_vers)


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
