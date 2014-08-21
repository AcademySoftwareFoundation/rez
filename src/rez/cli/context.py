'''
Print information about the current rez context, or a given context file.
'''

import os.path
import sys
import time
import tempfile
import subprocess
from uuid import uuid4
from rez.rex import OutputStyle
from rez.dot import save_graph, view_graph, prune_graph
from rez.vendor.version.requirement import Requirement


def setup_parser(parser, completions=False):
    from rez.system import system
    from rez.shells import get_shell_types

    formats = get_shell_types() + ['dict', 'actions']
    output_styles = [e.name for e in OutputStyle]

    parser.add_argument("--req", "--print-request", dest="print_request",
                        action="store_true",
                        help="print only the request list (not including implicits)")
    parser.add_argument("--res", "--print-resolve", dest="print_resolve",
                        action="store_true",
                        help="print only the resolve list")
    parser.add_argument("-t", "--print-tools", dest="print_tools", action="store_true",
                        help="print a list of the executables available in the context")
    parser.add_argument("--which", type=str, metavar="CMD",
                        help="locate a program within the context")
    parser.add_argument("-g", "--graph", action="store_true",
                        help="display the resolve graph as an image")
    parser.add_argument("--pg", "--print-graph", dest="print_graph", action="store_true",
                        help="print the resolve graph as a string")
    parser.add_argument("--wg", "--write-graph", dest="write_graph", type=str,
                        metavar='FILE', help="write the resolve graph to FILE")
    parser.add_argument("--pp", "--prune-package", dest="prune_pkg", metavar="PKG",
                        type=str, help="prune the graph down to PKG")
    parser.add_argument("-i", "--interpret", action="store_true",
                        help="interpret the context and print the resulting code")
    parser.add_argument("-f", "--format", type=str, choices=formats, default=system.shell,
                        help="print interpreted output in the given format. If "
                        "'dict', a dictionary of the resulting environment is "
                        "printed. Ignored if --interpret is not present "
                        " (default: %(default)s)")
    parser.add_argument("-s", "--style", type=str, default="file", choices=output_styles,
                        help="Set code output style. Ignored if --interpret is "
                        "not present (default: %(default)s)")
    parser.add_argument("--no-env", dest="no_env", action="store_true",
                        help="interpret the context in an empty environment")
    diff_action = parser.add_argument(
        "--diff", type=str, metavar="RXT",
        help="diff against the current context and the given context")
    parser.add_argument(
        "--peek", action="store_true",
        help="diff against the current context and a re-resolved copy of the "
        "current context, this shows how 'stale' the context is")
    RXT_action = parser.add_argument(
        "RXT", type=str, nargs='?',
        help="rex context file (current context if not supplied)")

    if completions:
        from rez.cli._complete_util import FilesCompleter
        rxt_completer = FilesCompleter(dirs=False, file_patterns=["*.rxt"])
        RXT_action.completer = rxt_completer
        diff_action.completer = rxt_completer


def command(opts, parser, extra_arg_groups=None):
    from rez.status import status
    from rez.util import pretty_env_dict, timings
    from rez.resolved_context import ResolvedContext

    timings.enabled = False
    rxt_file = opts.RXT if opts.RXT else status.context_file
    if not rxt_file:
        print >> sys.stderr, "not in a resolved environment context."
        sys.exit(1)

    rc = ResolvedContext.load(rxt_file)

    def _graph():
        if rc.has_graph:
            return rc.graph(as_dot=True)
        else:
            print >> sys.stderr, "The context does not contain a graph."
            sys.exit(1)

    parent_env = {} if opts.no_env else None

    if not opts.interpret:
        if opts.print_request:
            print " ".join(str(x) for x in rc.requested_packages(False))
        elif opts.print_resolve:
            print ' '.join(x.qualified_package_name for x in rc.resolved_packages)
        elif opts.print_tools:
            rc.print_tools()
        elif opts.diff:
            rc_other = ResolvedContext.load(opts.diff)
            rc.print_resolve_diff(rc_other)
        elif opts.peek:
            rc_new = ResolvedContext(rc.requested_packages(),
                                     package_paths=rc.package_paths,
                                     verbosity=opts.verbose)
            rc.print_resolve_diff(rc_new)
        elif opts.which:
            cmd = opts.which
            path = rc.which(cmd, parent_environ=parent_env)
            if path:
                print path
            else:
                print >> sys.stderr, "'%s' not found in the context" % cmd
        elif opts.print_graph:
            gstr = _graph()
            print gstr
        elif opts.graph or opts.write_graph:
            gstr = _graph()
            if opts.prune_pkg:
                req = Requirement(opts.prune_pkg)
                gstr = prune_graph(gstr, req.name)
            func = view_graph if opts.graph else save_graph
            func(gstr, dest_file=opts.write_graph)
        else:
            rc.print_info(verbosity=opts.verbose)
        return

    if opts.format == 'dict':
        env = rc.get_environ(parent_environ=parent_env)
        print pretty_env_dict(env)
    elif opts.format == 'actions':
        actions = rc.get_actions(parent_environ=parent_env)
        for action in actions:
            print str(action)
    else:
        code = rc.get_shell_code(shell=opts.format,
                                 parent_environ=parent_env,
                                 style=OutputStyle[opts.style])
        print code
