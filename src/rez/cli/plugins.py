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
Get a list of a package's plugins.
"""
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path")
    PKG_action = parser.add_argument(
        "PKG", type=str,
        help="package to list plugins for")

    if completions:
        from rez.cli._complete_util import PackageFamilyCompleter
        PKG_action.completer = PackageFamilyCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.package_search import get_plugins
    from rez.config import config
    import os
    import os.path
    import sys

    config.override("warn_none", True)

    if opts.paths is None:
        pkg_paths = None
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    pkgs_list = get_plugins(package_name=opts.PKG, paths=pkg_paths)
    if pkgs_list:
        print('\n'.join(pkgs_list))
    else:
        print("package '%s' has no plugins." % opts.PKG, file=sys.stderr)
