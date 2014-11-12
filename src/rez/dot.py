"""
Functions for manipulating dot-based resolve graphs.
"""
import re
import os.path
import subprocess
import sys
import tempfile
from rez.config import config
from rez.package_resources import PACKAGE_NAME_REGSTR
from rez.vendor.pydot import pydot
from rez.vendor.pygraph.readwrite.dot import write as write_dot
from rez.vendor.pygraph.readwrite.dot import read as read_dot
from rez.vendor.pygraph.algorithms.accessibility import accessibility


def prune_graph(graph_str, package_name):
    """Prune a package graph so it only contains nodes accessible from the
    given package.

    Args:
        graph_str (str): Dot-language graph string.
        package_name (str): Name of package of interest.

    Returns:
        Pruned graph, as a string.
    """
    # find nodes of interest
    g = read_dot(graph_str)
    regex = re.compile(PACKAGE_NAME_REGSTR)
    nodes = set()
    for node, attrs in g.node_attr.iteritems():
        attr = [x for x in attrs if x[0] == "label"]
        if attr:
            label = attr[0][1]
            match = regex.search(label)
            if match and match.group() == package_name:
                nodes.add(node)

    if not nodes:
        raise ValueError("The package %r does not appear in the graph."
                         % package_name)

    # find nodes upstream from these nodes
    g_rev = g.reverse()
    accessible_nodes = set()
    access = accessibility(g_rev)
    for node in nodes:
        nodes_ = access.get(node, [])
        accessible_nodes |= set(nodes_)

    # remove inaccessible nodes
    inaccessible_nodes = set(g.nodes()) - accessible_nodes
    for node in inaccessible_nodes:
        g.del_node(node)

    return write_dot(g)


def save_graph(graph_str, dest_file, fmt=None, image_ratio=None):
    """Render a graph to an image file.

    Args:
        graph_str (str): Dot-language graph string.
        dest_file (str): Filepath to save the graph to.
        fmt (str): Format, eg "png", "jpg".
        image_ratio (float): Image ratio.

    Returns:
        String representing format that was written, such as 'png'.
    """
    g = pydot.graph_from_dot_data(graph_str)

    # determine the dest format
    if fmt is None:
        fmt = os.path.splitext(dest_file)[1].lower().strip('.') or "png"
    if hasattr(g, "write_" + fmt):
        write_fn = getattr(g, "write_" + fmt)
    else:
        raise Exception("Unsupported graph format: '%s'" % fmt)

    if image_ratio:
        g.set_ratio(str(image_ratio))
    write_fn(dest_file)
    return fmt


def view_graph(graph_str, dest_file=None):
    """View a dot graph in an image viewer."""
    from rez.system import system
    from rez.config import config

    if (system.platform == "linux") and (not os.getenv("DISPLAY")):
        print >> sys.stderr, "Unable to open display."
        sys.exit(1)

    dest_file = _write_graph(graph_str, dest_file=dest_file)

    # view graph
    viewed = False
    prog = config.image_viewer or 'browser'
    print "loading image viewer (%s)..." % prog

    if config.image_viewer:
        proc = subprocess.Popen((config.image_viewer, dest_file))
        proc.wait()
        viewed = not bool(proc.returncode)

    if not viewed:
        import webbrowser
        webbrowser.open_new("file://" + dest_file)


def _write_graph(graph_str, dest_file=None):
    if not dest_file:
        tmpf = tempfile.mkstemp(prefix='resolve-dot-',
                                suffix='.' + config.dot_image_format)
        os.close(tmpf[0])
        dest_file = tmpf[1]

    print "rendering image to " + dest_file + "..."
    save_graph(graph_str, dest_file)
    return dest_file
