"""
Show information on a Rez context, usually the current context, if we are in
a Rez-resolved environment.
"""
import os
import os.path
import sys
import time
import textwrap
import tempfile
import subprocess
from uuid import uuid4
from rez import __version__
from rez.util import pretty_env_dict
from rez.resolved_context import ResolvedContext
from rez.shells import create_shell, get_shell_types
from rez.dot import save_graph
from rez.system import system
from rez.settings import settings



formats = get_shell_types() + ['dict']

current_rxt_file = os.getenv("REZ_RXT_FILE")
if current_rxt_file and not os.path.exists(current_rxt_file):
    current_rxt_file = None


def setup_parser(parser):
    parser.add_argument("--print-request", dest="print_request", action="store_true",
                        help="print only the request list, including implicits")
    parser.add_argument("--print-resolve", dest="print_resolve", action="store_true",
                        help="print only the resolve list")
    parser.add_argument("-g", "--graph", action="store_true",
                        help="display the resolve graph, as an image")
    parser.add_argument("--pg", "--print-graph", dest="print_graph", action="store_true",
                        help="print the resolve graph, as a string")
    parser.add_argument("--wg", "--write-graph", dest="write_graph", type=str,
                        metavar='FILE', help="write the resolve graph to FILE")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print more information about the context. "
                        "Ignored if --interpret is used.")
    parser.add_argument("-i", "--interpret", action="store_true",
                        help="interpret the context and print the resulting code")
    parser.add_argument("-f", "--format", type=str,
                        help="print interpreted output in the given format. If "
                        "None, the current shell language is used. If 'dict', "
                        "a dictionary of the resulting environment is printed. "
                        "Ignored if --interpret is False. "
                        "One of: %s" % str(formats))
    parser.add_argument("--no-env", dest="no_env", action="store_true",
                        help="interpret the context in an empty environment")
    parser.add_argument("FILE", type=str, nargs='?',
                        help='rex context file to execute')


# returns (filepath, must_cleanup)
def write_graph(graph_str, opts, is_current_context):
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
            if is_current_context:
                path = os.path.join(tmp_dir, "resolve-dot.%s" % fmt)
                if os.path.exists(path):
                    return path,False  # graph image already exists
                else:
                    dest_file = path
                    cleanup = False

        if dest_file is None:
            if tmp_dir:
                # hijack current env's tmpdir, so we don't have to clean up
                name = "resolve-dot-%s.%s" % (str(uuid4()).replace('-',''), fmt)
                dest_file = os.path.join(tmp_dir, name)
                cleanup = False
            else:
                tmpf = tempfile.mkstemp(prefix='resolve-dot-', suffix='.'+fmt)
                os.close(tmpf[0])
                dest_file = tmpf[1]

    print "rendering image to " + dest_file + "..."
    save_graph(graph_str, dest_file)
    return dest_file,cleanup


def view_graph(graph_str, opts, is_current_context):
    if (system.platform == "linux") and (not os.getenv("DISPLAY")):
        print >> sys.stderr, "Unable to open display."
        sys.exit(1)

    dest_file, cleanup = write_graph(graph_str, opts, is_current_context)

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
        if (t2-t1) < 1: # viewer is probably non-blocking
            # give app a chance to load image
            time.sleep(10)
        os.remove(dest_file)


def command(opts, parser=None):
    # are we reading the current context (ie are we inside a rez-env env)?
    is_current_context = False
    rxt_file = opts.FILE
    if rxt_file is None:
        rxt_file = current_rxt_file
        if rxt_file is None:
            print >> sys.stderr, textwrap.dedent(
                """
                running Rez v%s.
                not in a resolved environment context.
                """ % __version__).strip() + '\n'
            sys.exit(1)
        is_current_context = True

    rc = ResolvedContext.load(rxt_file)

    if not opts.interpret:
        if opts.print_request:
            print ' '.join(rc.added_implicit_packages + rc.requested_packages)
        elif opts.print_resolve:
            print ' '.join(x.short_name() for x in rc.resolved_packages)
        elif opts.print_graph:
            print rc.resolve_graph
        elif opts.graph:
            view_graph(rc.resolve_graph, opts, is_current_context)
        elif opts.write_graph:
            write_graph(rc.resolve_graph, opts, is_current_context)
        else:
            rc.print_info(verbose=opts.verbose)
            print
        return

    if opts.format not in (formats + [None]):
        parser.error("Invalid format specified, must be one of: %s" % str(formats))

    parent_env = {} if opts.no_env else None

    if opts.format == 'dict':
        env = rc.get_environ(parent_environ=parent_env)
        print pretty_env_dict(env)
    else:
        shell = opts.format or system.shell
        code = rc.get_shell_code(shell=shell, parent_environ=parent_env)
        print code
