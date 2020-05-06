# Copyright (c) 2007-2009 Pedro Matiello <pmatiello@gmail.com>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.


"""
Functions for reading and writing graphs in Dot language.

@sort: read, read_hypergraph, write, write_hypergraph
"""


# Imports
from rez.vendor.pygraph.classes.digraph import digraph
from rez.vendor.pygraph.classes.exceptions import InvalidGraphType
from rez.vendor.pygraph.classes.graph import graph
from rez.vendor.pygraph.classes.hypergraph import hypergraph
from rez.vendor.pydot import pydot

# Values
colors = ['aquamarine4', 'blue4', 'brown4', 'cornflowerblue', 'cyan4',
            'darkgreen', 'darkorange3', 'darkorchid4', 'darkseagreen4', 'darkslategray',
            'deeppink4', 'deepskyblue4', 'firebrick3', 'hotpink3', 'indianred3',
            'indigo', 'lightblue4', 'lightseagreen', 'lightskyblue4', 'magenta4',
            'maroon', 'palevioletred3', 'steelblue', 'violetred3']


def read(string):
    """
    Read a graph from a string in Dot language and return it. Nodes and edges specified in the
    input will be added to the current graph.

    @type  string: string
    @param string: Input string in Dot format specifying a graph.

    @rtype: graph
    @return: Graph
    """

    dotG = pydot.graph_from_dot_data(string)

    # This is awful, however there seems to be a major incompatibility with pygraph
    # and current pydot. Pydot now returns a list of graphs from a dot string. Rather
    # than possibly rewrite a big chunk of this lib, we'll just use the first graph.
    # Since rez only makes single graphs anyway, this should suffice.
    #
    # https://github.com/nerdvegas/rez/issues/884
    #
    # <hack>
    if isinstance(dotG, list):
        dotG = dotG[0]
    # </endhack>

    if (dotG.get_type() == "graph"):
        G = graph()
    elif (dotG.get_type() == "digraph"):
        G = digraph()
    elif (dotG.get_type() == "hypergraph"):
        return read_hypergraph(string)
    else:
        raise InvalidGraphType

    # Read nodes...
    # Note: If the nodes aren't explicitly listed, they need to be
    for each_node in dotG.get_nodes():
        G.add_node(each_node.get_name())
        for each_attr_key, each_attr_val in each_node.get_attributes().items():
            G.add_node_attribute(each_node.get_name(), (each_attr_key, each_attr_val))

    # Read edges...
    for each_edge in dotG.get_edges():
        # Check if the nodes have been added
        if not G.has_node(each_edge.get_source()):
            G.add_node(each_edge.get_source())
        if not G.has_node(each_edge.get_destination()):
            G.add_node(each_edge.get_destination())

        # See if there's a weight
        if 'weight' in each_edge.get_attributes().keys():
            _wt = each_edge.get_attributes()['weight']
        else:
            _wt = 1

        # See if there is a label
        if 'label' in each_edge.get_attributes().keys():
            _label = each_edge.get_attributes()['label']
        else:
            _label = ''

        G.add_edge((each_edge.get_source(), each_edge.get_destination()), wt = _wt, label = _label)

        for each_attr_key, each_attr_val in each_edge.get_attributes().items():
            if not each_attr_key in ['weight', 'label']:
                G.add_edge_attribute((each_edge.get_source(), each_edge.get_destination()), \
                                            (each_attr_key, each_attr_val))

    return G


def write(G, weighted=False):
    """
    Return a string specifying the given graph in Dot language.

    @type  G: graph
    @param G: Graph.

    @type  weighted: boolean
    @param weighted: Whether edges should be labelled with their weight.

    @rtype:  string
    @return: String specifying the graph in Dot Language.
    """
    dotG = pydot.Dot()

    if not 'name' in dir(G):
        dotG.set_name('graphname')
    else:
        dotG.set_name(G.name)

    if (isinstance(G, graph)):
        dotG.set_type('graph')
        directed = False
    elif (isinstance(G, digraph)):
        dotG.set_type('digraph')
        directed = True
    elif (isinstance(G, hypergraph)):
        return write_hypergraph(G)
    else:
        raise InvalidGraphType("Expected graph or digraph, got %s" %  repr(G) )

    for node in G.nodes():
        attr_list = {}
        for attr in G.node_attributes(node):
            attr_list[str(attr[0])] = str(attr[1])

        newNode = pydot.Node(str(node), **attr_list)

        dotG.add_node(newNode)

    # Pydot doesn't work properly with the get_edge, so we use
    #  our own set to keep track of what's been added or not.
    seen_edges = set([])
    for edge_from, edge_to in G.edges():
        if (str(edge_from) + "-" + str(edge_to)) in seen_edges:
            continue

        if (not directed) and (str(edge_to) + "-" + str(edge_from)) in seen_edges:
            continue

        attr_list = {}
        for attr in G.edge_attributes((edge_from, edge_to)):
            attr_list[str(attr[0])] = str(attr[1])

        if str(G.edge_label((edge_from, edge_to))):
            attr_list['label'] = str(G.edge_label((edge_from, edge_to)))

        elif weighted:
            attr_list['label'] = str(G.edge_weight((edge_from, edge_to)))

        if weighted:
            attr_list['weight'] = str(G.edge_weight((edge_from, edge_to)))

        newEdge = pydot.Edge(str(edge_from), str(edge_to), **attr_list)

        dotG.add_edge(newEdge)

        seen_edges.add(str(edge_from) + "-" + str(edge_to))

    return dotG.to_string()


def read_hypergraph(string):
    """
    Read a hypergraph from a string in dot format. Nodes and edges specified in the input will be
    added to the current hypergraph.

    @type  string: string
    @param string: Input string in dot format specifying a graph.

    @rtype:  hypergraph
    @return: Hypergraph
    """
    hgr = hypergraph()
    dotG = pydot.graph_from_dot_data(string)

    # Read the hypernode nodes...
    # Note 1: We need to assume that all of the nodes are listed since we need to know if they
    #           are a hyperedge or a normal node
    # Note 2: We should read in all of the nodes before putting in the links
    for each_node in dotG.get_nodes():
        if 'hypernode' == each_node.get('hyper_node_type'):
            hgr.add_node(each_node.get_name())
        elif 'hyperedge' == each_node.get('hyper_node_type'):
            hgr.add_hyperedge(each_node.get_name())

    # Now read in the links to connect the hyperedges
    for each_link in dotG.get_edges():
        if hgr.has_node(each_link.get_source()):
            link_hypernode = each_link.get_source()
            link_hyperedge = each_link.get_destination()
        elif hgr.has_node(each_link.get_destination()):
            link_hypernode = each_link.get_destination()
            link_hyperedge = each_link.get_source()
        hgr.link(link_hypernode, link_hyperedge)

    return hgr


def write_hypergraph(hgr, colored = False):
    """
    Return a string specifying the given hypergraph in DOT Language.

    @type  hgr: hypergraph
    @param hgr: Hypergraph.

    @type  colored: boolean
    @param colored: Whether hyperedges should be colored.

    @rtype:  string
    @return: String specifying the hypergraph in DOT Language.
    """
    dotG = pydot.Dot()

    if not 'name' in dir(hgr):
        dotG.set_name('hypergraph')
    else:
        dotG.set_name(hgr.name)

    colortable = {}
    colorcount = 0

    # Add all of the nodes first
    for node in hgr.nodes():
        newNode = pydot.Node(str(node), hyper_node_type = 'hypernode')

        dotG.add_node(newNode)

    for hyperedge in hgr.hyperedges():

        if (colored):
            colortable[hyperedge] = colors[colorcount % len(colors)]
            colorcount += 1

            newNode = pydot.Node(str(hyperedge), hyper_node_type = 'hyperedge', \
                                                 color = str(colortable[hyperedge]), \
                                                 shape = 'point')
        else:
            newNode = pydot.Node(str(hyperedge), hyper_node_type = 'hyperedge')

        dotG.add_node(newNode)

        for link in hgr.links(hyperedge):
            newEdge = pydot.Edge(str(hyperedge), str(link))
            dotG.add_edge(newEdge)

    return dotG.to_string()
