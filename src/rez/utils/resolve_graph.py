from rez.utils.graph_utils import _request_from_label


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


def _iter_init_request_nodes(graph):
    request_color = "#FFFFAA"  # NOTE: the color code is hardcoded in `solver`
    for node, attrs in graph.node_attr.items():
        for at in attrs:
            if at[0] == "fillcolor" and at[1] == request_color:
                yield node


def _get_node_label(graph, node):
    label_ = next(at[1] for at in graph.node_attr[node] if at[0] == "label")
    return _request_from_label(label_)


def _is_request_node(graph, node):
    style = next(at[1] for at in graph.node_attr[node] if at[0] == "style")
    return "dashed" in style


def _print_each_graph_edges(graph):
    """for debug"""
    for (from_, to_), properties in graph.edge_properties.items():
        edge_status = properties["label"]
        from_name = _get_node_label(graph, from_)
        to_name = _get_node_label(graph, to_)
        print("%s -> %s  %s" % (from_name, to_name, edge_status))
