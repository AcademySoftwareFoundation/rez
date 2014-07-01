from rez.system import system
from rez.settings import settings
from rez.cli._util import current_rxt_file
import os
import subprocess
import tempfile
import time


# returns (filepath, must_cleanup)
def write_graph(graph_str, write_graph=None, prune_pkg=None):
    dest_file = None
    tmp_dir = None
    cleanup = True

    if write_graph:
        dest_file = write_graph
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
    save_graph(graph_str, dest_file, prune_to_package=prune_pkg,
               prune_to_conflict=False)
    return dest_file, cleanup


def view_graph(graph_str, write_graph_=None, prune_pkg=None):

    if (system.platform == "linux") and (not os.getenv("DISPLAY")):
        print >> sys.stderr, "Unable to open display."
        sys.exit(1)

    dest_file, cleanup = write_graph(graph_str,  write_graph=write_graph_, prune_pkg=prune_pkg)

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
