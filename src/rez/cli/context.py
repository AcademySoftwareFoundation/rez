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
from rez.system import system
from rez.settings import settings



current_rxt_file = os.getenv("REZ_RXT_FILE")
if current_rxt_file and not os.path.exists(current_rxt_file):
    current_rxt_file = None


# returns (filepath, must_cleanup)
def write_graph(graph_str, opts):
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
            name = "resolve-dot-%s.%s" % (str(uuid4()).replace('-',''), fmt)
            dest_file = os.path.join(tmp_dir, name)
            cleanup = False
        else:
            tmpf = tempfile.mkstemp(prefix='resolve-dot-', suffix='.'+fmt)
            os.close(tmpf[0])
            dest_file = tmpf[1]

    from rez.dot import save_graph
    print "rendering image to " + dest_file + "..."
    save_graph(graph_str, dest_file, prune_to_package=opts.prune_pkg,
               prune_to_conflict=opts.prune_conflict)
    return dest_file,cleanup


def view_graph(graph_str, opts):
    if (system.platform == "linux") and (not os.getenv("DISPLAY")):
        print >> sys.stderr, "Unable to open display."
        sys.exit(1)

    dest_file,cleanup = write_graph(graph_str, opts)

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

    rc = ResolvedContext.load(rxt_file)

    def _check_graph(g):
        if g is None:
            print >> sys.stderr, "The context does not contain a graph."
            sys.exit(0)

    if not opts.interpret:
        if opts.print_request:
            print ' '.join(rc.added_implicit_packages + rc.requested_packages)
        elif opts.print_resolve:
            print ' '.join(x.short_name() for x in rc.resolved_packages)
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
            print
        return

    parent_env = {} if opts.no_env else None

    if opts.format == 'dict':
        env = rc.get_environ(parent_environ=parent_env)
        print pretty_env_dict(env)
    else:
        code = rc.get_shell_code(shell=opts.format, parent_environ=parent_env)
        print code
