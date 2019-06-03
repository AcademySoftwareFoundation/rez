"""
Perform a reverse package dependency lookup.
"""
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-d", "--depth", type=int,
        help="dependency tree depth limit")
    parser.add_argument(
        "--paths", type=str,
        help="set package search path")
    parser.add_argument(
        "-b", "--build-requires", action="store_true",
        help="Include build requirements")
    parser.add_argument(
        "-p", "--private-build-requires", action="store_true",
        help="Include private build requirements of PKG, if any")
    parser.add_argument(
        "-g", "--graph", action="store_true",
        help="display the dependency tree as an image")
    parser.add_argument(
        "--pg", "--print-graph", dest="print_graph", action="store_true",
        help="print the dependency tree as a string")
    parser.add_argument(
        "--wg", "--write-graph", dest="write_graph", metavar='FILE',
        help="write the dependency tree to FILE")
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="don't print progress bar or depth indicators")
    PKG_action = parser.add_argument(
        "PKG",
        help="package that other packages depend on")

    if completions:
        from rez.cli._complete_util import PackageFamilyCompleter
        PKG_action.completer = PackageFamilyCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.package_search import get_reverse_dependency_tree
    from rez.utils.graph_utils import save_graph, view_graph
    from rez.config import config
    from rez.vendor.pygraph.readwrite.dot import write as write_dot
    import os
    import os.path

    config.override("warn_none", True)
    config.override("show_progress", (not opts.quiet))

    if opts.paths is None:
        pkg_paths = None
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    pkgs_list, g = get_reverse_dependency_tree(
        package_name=opts.PKG,
        depth=opts.depth,
        paths=pkg_paths,
        build_requires=opts.build_requires,
        private_build_requires=opts.private_build_requires)

    if opts.graph or opts.print_graph or opts.write_graph:
        gstr = write_dot(g)
        if opts.print_graph:
            print(gstr)
        elif opts.write_graph:
            save_graph(gstr, dest_file=opts.write_graph)
        else:
            view_graph(gstr)
        return 0

    for i, pkgs in enumerate(pkgs_list):
        if opts.quiet:
            toks = pkgs
        else:
            toks = ["#%d:" % i] + pkgs
        print(' '.join(toks))


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
