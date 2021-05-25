"""
Functions for manipulating dot-based resolve graphs.
"""
from __future__ import print_function

import os.path
import sys
import tempfile
from ast import literal_eval
from rez.config import config
from rez.vendor.pydot import pydot
from rez.utils.execution import Popen
from rez.utils.formatting import PackageRequest
from rez.exceptions import PackageRequestError
from rez.vendor.pygraph.readwrite.dot import read as read_dot
from rez.vendor.pygraph.algorithms.accessibility import accessibility
from rez.vendor.pygraph.classes.digraph import digraph
from rez.vendor.six import six


basestring = six.string_types[0]


def read_graph_from_string(txt):
    """Read a graph from a string, either in dot format, or our own
    compressed format.

    Returns:
        `pygraph.digraph`: Graph object.
    """
    if not txt.startswith('{'):
        return read_dot(txt)  # standard dot format

    def conv(value):
        if isinstance(value, basestring):
            return '"' + value + '"'
        else:
            return value

    # our compacted format
    doc = literal_eval(txt)
    g = digraph()

    for attrs, values in doc.get("nodes", []):
        attrs = [(k, conv(v)) for k, v in attrs]

        for value in values:
            if isinstance(value, basestring):
                node_name = value
                attrs_ = attrs
            else:
                node_name, label = value
                attrs_ = attrs + [("label", conv(label))]

            g.add_node(node_name, attrs=attrs_)

    for attrs, values in doc.get("edges", []):
        attrs_ = [(k, conv(v)) for k, v in attrs]

        for value in values:
            if len(value) == 3:
                edge = value[:2]
                label = value[-1]
            else:
                edge = value
                label = ''

            g.add_edge(edge, label=label, attrs=attrs_)

    return g


def write_compacted(g):
    """Write a graph in our own compacted format.

    Returns:
        str.
    """
    d_nodes = {}
    d_edges = {}

    def conv(value):
        if isinstance(value, basestring):
            return value.strip('"')
        else:
            return value

    for node in g.nodes():
        label = None
        attrs = []

        for k, v in sorted(g.node_attributes(node)):
            v_ = conv(v)
            if k == "label":
                label = v_
            else:
                attrs.append((k, v_))

        value = (node, label) if label else node
        d_nodes.setdefault(tuple(attrs), []).append(value)

    for edge in g.edges():
        attrs = [(k, conv(v)) for k, v in sorted(g.edge_attributes(edge))]
        label = str(g.edge_label(edge))
        value = tuple(list(edge) + [label]) if label else edge
        d_edges.setdefault(tuple(attrs), []).append(tuple(value))

    doc = dict(nodes=list(d_nodes.items()), edges=list(d_edges.items()))
    contents = str(doc)
    return contents


def write_dot(g):
    """Replacement for pygraph.readwrite.dot.write, which is dog slow.

    Note:
        This isn't a general replacement. It will work for the graphs that
        Rez generates, but there are no guarantees beyond that.

    Args:
        g (`pygraph.digraph`): Input graph.

    Returns:
        str: Graph in dot format.
    """
    lines = ["digraph g {"]

    def attrs_txt(items):
        if items:
            txt = ", ".join(('%s="%s"' % (k, str(v).strip('"')))
                            for k, v in items)
            return '[' + txt + ']'
        else:
            return ''

    for node in g.nodes():
        atxt = attrs_txt(g.node_attributes(node))
        txt = "%s %s;" % (node, atxt)
        lines.append(txt)

    for e in g.edges():
        edge_from, edge_to = e
        attrs = g.edge_attributes(e)

        label = str(g.edge_label(e))
        if label:
            attrs.append(("label", label))

        atxt = attrs_txt(attrs)
        txt = "%s -> %s %s;" % (edge_from, edge_to, atxt)
        lines.append(txt)

    lines.append("}")
    return '\n'.join(lines)


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
    nodes = set()

    for node, attrs in g.node_attr.items():
        attr = [x for x in attrs if x[0] == "label"]
        if attr:
            label = attr[0][1]
            try:
                req_str = _request_from_label(label)
                request = PackageRequest(req_str)
            except PackageRequestError:
                continue

            if request.name == package_name:
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

    # Disconnected edges can result in multiple graphs. We should never see
    # this - it's a bug in graph generation if we do.
    #
    graphs = pydot.graph_from_dot_data(graph_str)

    if not graphs:
        raise RuntimeError("No graph generated")

    if len(graphs) > 1:
        path, ext = os.path.splitext(dest_file)
        dest_files = []

        for i, g in enumerate(graphs):
            try:
                dest_file_ = "%s.%d%s" % (path, i + 1, ext)
                save_graph_object(g, dest_file_, fmt, image_ratio)
                dest_files.append(dest_file_)
            except:
                pass

        raise RuntimeError(
            "More than one graph was generated; this probably indicates a bug "
            "in graph generation. Graphs were written to %r" % dest_files
        )

    # write the graph
    return save_graph_object(graphs[0], dest_file, fmt, image_ratio)


def save_graph_object(g, dest_file, fmt=None, image_ratio=None):
    """Like `save_graph`, but takes a pydot Dot object.
    """

    # determine the dest format
    if fmt is None:
        fmt = os.path.splitext(dest_file)[1].lower().strip('.') or "png"

    if hasattr(g, "write_" + fmt):
        write_fn = getattr(g, "write_" + fmt)
    else:
        raise RuntimeError("Unsupported graph format: '%s'" % fmt)

    if image_ratio:
        g.set_ratio(str(image_ratio))
    write_fn(dest_file)
    return fmt


def view_graph(graph_str, dest_file=None):
    """View a dot graph in an image viewer."""
    from rez.system import system
    from rez.config import config

    if (system.platform == "linux") and (not os.getenv("DISPLAY")):
        print("Unable to open display.", file=sys.stderr)
        sys.exit(1)

    dest_file = _write_graph(graph_str, dest_file=dest_file)

    # view graph
    viewed = False
    prog = config.image_viewer or 'browser'
    print("loading image viewer (%s)..." % prog)

    if config.image_viewer:
        with Popen([config.image_viewer, dest_file]) as p:
            p.wait()
        viewed = not bool(p.returncode)

    if not viewed:
        import webbrowser
        webbrowser.open_new("file://" + dest_file)


def _write_graph(graph_str, dest_file=None):
    if not dest_file:
        tmpf = tempfile.mkstemp(prefix='resolve-dot-',
                                suffix='.' + config.dot_image_format)
        os.close(tmpf[0])
        dest_file = tmpf[1]

    print("rendering image to " + dest_file + "...")
    save_graph(graph_str, dest_file)
    return dest_file


# converts string like '"PyQt-4.8.0[1]"' to 'PyQt-4.8.0'
def _request_from_label(label):
    return label.strip('"').strip("'").rsplit('[', 1)[0]


def _get_node_label(graph, node):
    label_ = next(at[1] for at in graph.node_attr[node] if at[0] == "label")
    return _request_from_label(label_)


def _is_request_node(graph, node):
    style = next(at[1] for at in graph.node_attr[node] if at[0] == "style")
    return "dashed" in style


def _iter_init_request_nodes(graph):
    request_color = "#FFFFAA"  # NOTE: the color code is hardcoded in `solver`
    for node, attrs in graph.node_attr.items():
        for at in attrs:
            if at[0] == "fillcolor" and at[1] == request_color:
                yield node


def failure_detail_from_graph(graph):
    """Generate detailed resolve failure messages from graph

    Args:
        graph (rez.vendor.pygraph.classes.digraph.digraph): context graph object

    """
    # Base on `rez.solver._ResolvePhase.get_graph()`
    #   the failure reason has three types:
    #
    #   * DependencyConflicts
    #       which have "conflict" edge in graph
    #
    #   * TotalReduction
    #       which have "conflict" edge and may also have "reduct" edge in graph
    #
    #   * Cycle
    #       which have "cycle" edge in graph
    #
    #   so we find cycle edge first, and try other if not found.
    #

    # find cycle
    cycled_edge = next((k for k, v in graph.edge_properties.items()
                        if v["label"] == "CYCLE"), None)
    if cycled_edge:
        return _cycled_detail_from_graph(graph, cycled_edge)

    # find conflict
    conflicted_edge = next((k for k, v in graph.edge_properties.items()
                            if v["label"] == "CONFLICT"), None)
    if conflicted_edge:
        return _conflicted_detail_from_graph(graph, conflicted_edge)

    # should be a healthy graph
    return ""


def _cycled_detail_from_graph(graph, cycled_edge):
    """Find all initial requests, and walk down till circle back"""

    messages = ["Resolve paths starting from initial requests to cycle:"]

    for init_request in _iter_init_request_nodes(graph):
        node = init_request
        visited = list()
        while True:
            visited.append(node)
            down = next((ne for ne in graph.node_neighbors[node]), None)
            if down in cycled_edge:
                visited.append(down)
                break
            if down is None:
                break

            node = down

        line = "  %s" % _get_node_label(graph, visited[0])  # init request
        for node in visited[1:]:
            # should be more readable if opt-out requests
            if not _is_request_node(graph, node):
                line += " --> %s" % _get_node_label(graph, node)

        messages.append(line)

    return "\n".join(messages)


def _conflicted_detail_from_graph(graph, conflicted_edge):
    """Find all initial requests, and walk down till in conflicted edge"""

    messages = ["Resolve paths starting from initial requests to conflict:"]

    for init_request in _iter_init_request_nodes(graph):
        node = init_request
        visited = list()
        while True:
            visited.append(node)
            down = next((ne for ne in graph.node_neighbors[node]), None)
            if down is None:
                break

            node = down

        line = "  %s" % _get_node_label(graph, visited[0])  # init request
        for node in visited[1:]:
            # should be more readable if opt-out requests
            if not _is_request_node(graph, node):
                line += " --> %s" % _get_node_label(graph, node)

            # show conflicted request at the end
            if _is_request_node(graph, node) and node in conflicted_edge:
                line += " --> %s" % _get_node_label(graph, node)
                break

        messages.append(line)

    return "\n".join(messages)


def _print_each_graph_edges(graph):
    """for debug"""
    for (from_, to_), properties in graph.edge_properties.items():
        edge_status = properties["label"]
        from_name = _get_node_label(graph, from_)
        to_name = _get_node_label(graph, to_)
        print("%s -> %s  %s" % (from_name, to_name, edge_status))


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
