"""
Reverse dependency lookup.
"""
import os
import os.path


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-d", "--depth", type=int,
        help="dependency tree depth limit")
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path")
    parser.add_argument(
        "-g", "--graph", action="store_true",
        help="display the dependency tree as an image")
    parser.add_argument(
        "--pg", "--print-graph", dest="print_graph", action="store_true",
        help="print the dependency tree as a string")
    parser.add_argument(
        "--wg", "--write-graph", dest="write_graph", type=str, metavar='FILE',
        help="write the dependency tree to FILE")
    PKG_action = parser.add_argument(
        "PKG", type=str,
        help="package that other packages depend on")

    if completions:
        from rez.cli._complete_util import PackageFamilyCompleter
        PKG_action.completer = PackageFamilyCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.package_search import get_reverse_dependency_tree
    from rez.dot import save_graph, view_graph
    from rez.config import config
    from rez.colorize import heading, Printer
    from rez.vendor.pygraph.readwrite.dot import write as write_dot

    config.override("warn_none", True)

    if opts.paths is None:
        pkg_paths = None
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    pkgs_list, g = get_reverse_dependency_tree(
        package_name=opts.PKG,
        depth=opts.depth,
        paths=pkg_paths)

    if opts.graph or opts.print_graph or opts.write_graph:
        gstr = write_dot(g)
        if opts.print_graph:
            print gstr
        elif opts.write_graph:
            save_graph(gstr, dest_file=opts.write_graph)
        else:
            view_graph(gstr)
        return 0

    _pr = Printer()
    _pr()
    for i, pkgs in enumerate(pkgs_list):
        _pr("depth %d:" % i, heading)
        _pr(" ".join(pkgs))
