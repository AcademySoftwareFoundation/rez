'''
Print information about the current rez context, or a given context file.
'''
from __future__ import print_function

# Disable context tracking. Use of rez-context doesn't really indicate usage of
# the packages in the context; and tracking this causes doubling up, ie most
# rez-env invocations do a rez-context immediately after. So turning this off
# cuts down on the amount of data getting tracked, and is more indicative of
# actual package use.
#
import os
os.environ["REZ_CONTEXT_TRACKING_HOST"] = ''

import json
import sys
from rez.rex import OutputStyle


def setup_parser(parser, completions=False):
    from rez.system import system
    from rez.shells import get_shell_types

    formats = get_shell_types() + ['dict', 'table']
    if json is not None:
        formats.append('json')

    output_styles = [e.name for e in OutputStyle]

    parser.add_argument(
        "--req", "--print-request", dest="print_request",
        action="store_true",
        help="print only the request list (not including implicits)")
    parser.add_argument(
        "--res", "--print-resolve", dest="print_resolve",
        action="store_true",
        help="print only the resolve list")
    parser.add_argument(
        "--so", "--source-order", dest="source_order", action="store_true",
        help="print resolved packages in order they are sorted, rather than "
        "alphabetical order")
    parser.add_argument(
        "--su", "--show-uris", dest="show_uris", action="store_true",
        help="list resolved package's URIs, rather than the default 'root' "
        "filepath")
    parser.add_argument(
        "-t", "--tools", action="store_true",
        help="print a list of the executables available in the context")
    parser.add_argument(
        "--which", type=str, metavar="CMD",
        help="locate a program within the context")
    parser.add_argument(
        "-g", "--graph", action="store_true",
        help="display the resolve graph as an image")
    parser.add_argument(
        "--pg", "--print-graph", dest="print_graph", action="store_true",
        help="print the resolve graph as a string")
    parser.add_argument(
        "--wg", "--write-graph", dest="write_graph", type=str,
        metavar='FILE', help="write the resolve graph to FILE")
    parser.add_argument(
        "--pp", "--prune-package", dest="prune_pkg", metavar="PKG",
        type=str, help="prune the graph down to PKG")
    parser.add_argument(
        "-i", "--interpret", action="store_true",
        help="interpret the context and print the resulting code")
    parser.add_argument(
        "-f", "--format", type=str, choices=formats, default=system.shell,
        help="print interpreted output in the given format. Ignored if "
        "--interpret is not present (default: %(default)s). If one of "
        "table, dict or json, the environ dict is printed.")
    parser.add_argument(
        "-s", "--style", type=str, default="file", choices=output_styles,
        help="Set code output style. Ignored if --interpret is not present "
        "(default: %(default)s)")
    parser.add_argument(
        "--no-env", dest="no_env", action="store_true",
        help="interpret the context in an empty environment")
    diff_action = parser.add_argument(
        "--diff", type=str, metavar="RXT",
        help="diff the current context against the given context")
    parser.add_argument(
        "--fetch", action="store_true",
        help="diff the current context against a re-resolved copy of the "
        "current context")
    RXT_action = parser.add_argument(
        "RXT", type=str, nargs='?',
        help="rez context file (current context if not supplied). Use '-' to "
        "read the context from stdin")

    if completions:
        from rez.cli._complete_util import FilesCompleter
        rxt_completer = FilesCompleter(dirs=False, file_patterns=["*.rxt"])
        RXT_action.completer = rxt_completer
        diff_action.completer = rxt_completer


def command(opts, parser, extra_arg_groups=None):
    from rez.status import status
    from rez.utils.formatting import columnise, PackageRequest
    from rez.resolved_context import ResolvedContext
    from rez.utils.graph_utils import save_graph, view_graph, prune_graph
    from pprint import pformat

    rxt_file = opts.RXT if opts.RXT else status.context_file
    if not rxt_file:
        print("not in a resolved environment context.", file=sys.stderr)
        sys.exit(1)

    if rxt_file == '-':  # read from stdin
        rc = ResolvedContext.read_from_buffer(sys.stdin, 'STDIN')
    else:
        rc = ResolvedContext.load(rxt_file)

    def _graph():
        if rc.has_graph:
            return rc.graph(as_dot=True)
        else:
            print("The context does not contain a graph.", file=sys.stderr)
            sys.exit(1)

    parent_env = {} if opts.no_env else None

    if not opts.interpret:
        if opts.print_request:
            print(" ".join(str(x) for x in rc.requested_packages(False)))
        elif opts.print_resolve:
            print(' '.join(x.qualified_package_name for x in rc.resolved_packages))
        elif opts.tools:
            rc.print_tools()
        elif opts.diff:
            rc_other = ResolvedContext.load(opts.diff)
            rc.print_resolve_diff(rc_other, True)
        elif opts.fetch:
            rc_new = ResolvedContext(rc.requested_packages(),
                                     package_paths=rc.package_paths,
                                     verbosity=opts.verbose)
            rc.print_resolve_diff(rc_new, heading=("current", "updated"))
        elif opts.which:
            cmd = opts.which
            path = rc.which(cmd, parent_environ=parent_env)
            if path:
                print(path)
            else:
                print("'%s' not found in the context" % cmd, file=sys.stderr)
        elif opts.print_graph:
            gstr = _graph()
            print(gstr)
        elif opts.graph or opts.write_graph:
            gstr = _graph()
            if opts.prune_pkg:
                req = PackageRequest(opts.prune_pkg)
                gstr = prune_graph(gstr, req.name)
            func = view_graph if opts.graph else save_graph
            func(gstr, dest_file=opts.write_graph)
        else:
            rc.print_info(verbosity=opts.verbose,
                          source_order=opts.source_order,
                          show_resolved_uris=opts.show_uris)
        return

    if opts.format in ("dict", "table", "json"):
        env = rc.get_environ(parent_environ=parent_env)

        if opts.format == 'table':
            rows = [x for x in sorted(env.items())]
            print('\n'.join(columnise(rows)))
        elif opts.format == 'dict':
            print(pformat(env))
        else:  # json
            print(json.dumps(env, sort_keys=True, indent=4))
    else:
        code = rc.get_shell_code(shell=opts.format,
                                 parent_environ=parent_env,
                                 style=OutputStyle[opts.style])
        print(code)


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
