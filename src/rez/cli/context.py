'''
Print information about the current rez context, or a given context file.
'''

import os.path
import sys
import time
import tempfile
import subprocess
from uuid import uuid4

# returns (filepath, must_cleanup)
def write_graph(graph_str, opts):
    from rez.settings import settings
    from rez.cli._util import current_rxt_file
    dest_file = None
    tmp_dir = None
    cleanup = True

    if opts.write_graph:
        dest_file = opts.write_graph
        cleanup = False
    else:
        fmt = settings.dot_image_format

        if current_rxt_file:
            tmp_dir = os.path.dirname(current_rxt_file)
            if not os.path.exists(tmp_dir):
                tmp_dir = None

        if tmp_dir:
            # hijack current env's tmpdir, so we don't have to clean up
            name = "resolve-dot-%s.%s" % (str(uuid4()).replace('-', ''), fmt)
            dest_file = os.path.join(tmp_dir, name)
            cleanup = False
        else:
            tmpf = tempfile.mkstemp(prefix='resolve-dot-', suffix='.' + fmt)
            os.close(tmpf[0])
            dest_file = tmpf[1]

    from rez.dot import save_graph
    print "rendering image to " + dest_file + "..."
    save_graph(graph_str, dest_file, prune_to_package=opts.prune_pkg,
               prune_to_conflict=opts.prune_conflict)
    return dest_file, cleanup


def view_graph(graph_str, opts):
    from rez.system import system
    from rez.settings import settings

    if (system.platform == "linux") and (not os.getenv("DISPLAY")):
        print >> sys.stderr, "Unable to open display."
        sys.exit(1)

    dest_file, cleanup = write_graph(graph_str, opts)

    # view graph
    t1 = time.time()
    viewed = False
    prog = settings.image_viewer or 'browser'
    print "loading image viewer (%s)..." % prog

    if settings.image_viewer:
        proc = subprocess.Popen((settings.image_viewer, dest_file))
        proc.wait()
        viewed = not bool(proc.returncode)

    if not viewed:
        import webbrowser
        webbrowser.open_new("file://" + dest_file)

    if cleanup:
        # hacky - gotta delete tmp file, but hopefully not before app has loaded it
        t2 = time.time()
        if (t2 - t1) < 1: # viewer is probably non-blocking
            # give app a chance to load image
            time.sleep(10)
        os.remove(dest_file)


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

    formats = get_shell_types() + ['dict']

    parser.add_argument("--req", "--print-request", dest="print_request",
                        action="store_true",
                        help="print only the request list, including implicits")
    parser.add_argument("--res", "--print-resolve", dest="print_resolve",
                        action="store_true",
                        help="print only the resolve list")
    parser.add_argument("-t", "--print-tools", dest="print_tools", action="store_true",
                        help="print a list of the executables available in the context")
    parser.add_argument("-g", "--graph", action="store_true",
                        help="display the resolve graph as an image")
    parser.add_argument("--pg", "--print-graph", dest="print_graph", action="store_true",
                        help="print the resolve graph as a string")
    parser.add_argument("--wg", "--write-graph", dest="write_graph", type=str,
                        metavar='FILE', help="write the resolve graph to FILE")
    parser.add_argument("--pp", "--prune-package", dest="prune_pkg", metavar="PKG",
                        type=str, help="prune the graph down to PKG")
    parser.add_argument("--pc", "--prune-conflict", dest="prune_conflict", action="store_true",
                        help="prune the graph down to show conflicts only")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print more information about the context. "
                        "Ignored if --interpret is used.")
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

def command(opts, parser=None):
    from rez.cli._util import get_rxt_file, current_rxt_file
    from rez.util import pretty_env_dict
    from rez.resolved_context import ResolvedContext

    rxt_file = get_rxt_file(opts.FILE)
    rc = ResolvedContext.load(rxt_file)

    def _check_graph(g):
        if g is None:
            print >> sys.stderr, "The context does not contain a graph."
            sys.exit(1)

    if not opts.interpret:
        if opts.print_request:
            print ' '.join(rc.added_implicit_packages + rc.requested_packages)
        elif opts.print_resolve:
            print ' '.join(x.short_name() for x in rc.resolved_packages)
        elif opts.print_tools:
            print_tools(rc)
        elif opts.print_graph:
            _check_graph(rc.resolve_graph)
            print rc.resolve_graph
        elif opts.graph:
            _check_graph(rc.resolve_graph)
            view_graph(rc.resolve_graph, opts)
        elif opts.write_graph:
            _check_graph(rc.resolve_graph)
            write_graph(rc.resolve_graph, opts)
        else:
            rc.print_info(verbose=opts.verbose)
            if opts.verbose and (rxt_file == current_rxt_file):
                print
                print "rxt file:\n%s" % rxt_file
            print
        return

    parent_env = {} if opts.no_env else None

    if opts.format == 'dict':
        env = rc.get_environ(parent_environ=parent_env)
        print pretty_env_dict(env)
    else:
        code = rc.get_shell_code(shell=opts.format, parent_environ=parent_env)
        print code
