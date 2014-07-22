'''
Print information about the current rez context, or a given context file.
'''

import os.path
import sys
import time
import tempfile
import subprocess
from uuid import uuid4
from rez import __version__
from rez.config import config
from rez.dot import write_graph, view_graph, prune_graph
from rez.vendor.version.requirement import Requirement


def print_tools(rc):
    from rez.util import columnise
    keys = rc.get_key("tools")
    if keys:
        rows = [
            ["TOOL", "PACKAGE"],
            ["----", "-------"]]
        for pkg, tools in sorted(keys.items()):
            for tool in sorted(tools):
                rows.append([tool, pkg])

    strs = columnise(rows)
    print '\n'.join(strs)
    print


def setup_parser(parser):
    from rez.system import system
    from rez.shells import get_shell_types

    formats = get_shell_types() + ['dict', 'actions']

    parser.add_argument("--req", "--print-request", dest="print_request",
                        action="store_true",
                        help="print only the request list, including implicits")
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
    parser.add_argument("-f", "--format", type=str, choices=formats,
                        help="print interpreted output in the given format. If "
                        "None, the current shell language (%s) is used. If 'dict', "
                        "a dictionary of the resulting environment is printed. "
                        "Ignored if --interpret is False" % system.shell)
    parser.add_argument("--no-env", dest="no_env", action="store_true",
                        help="interpret the context in an empty environment")
    parser.add_argument("FILE", type=str, nargs='?',
                        help="rex context file (current context if not supplied)")


def command(opts, parser):
    from rez.env import get_context_file
    from rez.util import pretty_env_dict, timings
    from rez.resolved_context import ResolvedContext

    timings.enabled = False
    rxt_file = opts.FILE if opts.FILE else get_context_file()
    if not rxt_file:
        print >> sys.stderr, "running Rez v%s.\n" \
            "not in a resolved environment context." % __version__
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
            print ' '.join(rc.added_implicit_packages + rc.requested_packages)
        elif opts.print_resolve:
            print ' '.join(x.short_name() for x in rc.resolved_packages)
        elif opts.print_tools:
            print_tools(rc)
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
            func = view_graph if opts.graph else write_graph
            func(gstr, dest_file=opts.write_graph)
        else:
            rc.print_info(verbose=opts.verbose)
        return

    if opts.format == 'dict':
        env = rc.get_environ(parent_environ=parent_env)
        print pretty_env_dict(env)
    elif opts.format == 'actions':
        actions = rc.get_actions(parent_environ=parent_env)
        for action in actions:
            print str(action)
    else:
        code = rc.get_shell_code(shell=opts.format, parent_environ=parent_env)
        print code
