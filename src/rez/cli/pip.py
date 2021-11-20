# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
Install a pip-compatible python package, and its dependencies, as rez packages.
"""
from __future__ import print_function
from argparse import REMAINDER
import logging


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--python-version", dest="py_ver", metavar="VERSION",
        help="python version (rez package) to use, default is latest. Note "
        "that the pip package(s) will be installed with a dependency on "
        "python-MAJOR.MINOR.")
    parser.add_argument(
        "--pip-version", dest="pip_ver", metavar="VERSION",
        help="pip version (rez package) to use, default is latest."
        " This option is deprecated and will be removed in the future.")
    parser.add_argument(
        "-i", "--install", action="store_true",
        help="install the package")
    parser.add_argument(
        "-r", "--release", action="store_true",
        help="install as released package; if not set, package is installed "
        "locally only")
    parser.add_argument(
        "-p", "--prefix", type=str, metavar='PATH',
        help="install to a custom package repository path.")
    parser.add_argument(
        "PACKAGE",
        help="package to install or archive/url to install from")
    parser.add_argument(
        "-e", "--extra", nargs=REMAINDER,
        help="extra args passthrough to pip install (overrides pre-configured args if specified)"
    )


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config

    # debug_package_release is used by rez.pip._verbose
    config.debug_package_release = config.debug_package_release or opts.verbose
    if not config.debug_package_release:
        # Prevent other rez.* loggers from printing debugs
        logging.getLogger('rez').setLevel(logging.INFO)

    from rez.pip import pip_install_package
    import warnings

    # a bit weird, but there used to be more options. Leave like this for now
    if not opts.install:
        parser.error("Expected one of: --install")

    if opts.pip_ver:
        with warnings.catch_warnings():
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")
            warnings.warn(
                "The option --pip-version is deprecated and will be removed in a future version",
                category=DeprecationWarning
            )

    pip_install_package(
        opts.PACKAGE,
        pip_version=opts.pip_ver,
        python_version=opts.py_ver,
        release=opts.release,
        prefix=opts.prefix,
        extra_args=opts.extra)
