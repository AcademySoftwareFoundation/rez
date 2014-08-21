# Copyright (c) 2007-2009 Pedro Matiello <pmatiello@gmail.com>
#                         Johannes Reinhardt <jreinhardt@ist-dein-freund.de>
#                         Nathan Davis <davisn90210@gmail.com>
#                         Zsolt Haraszti <zsolt@drawwell.net>
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
Graph class
"""


# Imports
from rez.vendor.pygraph.classes.exceptions import AdditionError
from rez.vendor.pygraph.mixins.labeling import labeling
from rez.vendor.pygraph.mixins.common import common
from rez.vendor.pygraph.mixins.basegraph import basegraph


class graph(basegraph, common, labeling):
    """
    Graph class.
    
    Graphs are built of nodes and edges.

    @sort:  __eq__, __init__, __ne__, add_edge, add_node, del_edge, del_node, edges, has_edge, has_node,
    neighbors, node_order, nodes
    """
    
    DIRECTED = False


    def __init__(self):
        """
        Initialize a graph.
        """
        common.__init__(self)
        labeling.__init__(self)
        self.node_neighbors = {}     # Pairing: Node -> Neighbors
    
    def nodes(self):
        """
        Return node list.

        @rtype:  list
        @return: Node list.
        """
        return list(self.node_neighbors.keys())


    def neighbors(self, node):
        """
        Return all nodes that are directly accessible from given node.

        @type  node: node
        @param node: Node identifier

        @rtype:  list
        @return: List of nodes directly accessible from given node.
        """
        return self.node_neighbors[node]
    
    def edges(self):
        """
        Return all edges in the graph.
        
        @rtype:  list
        @return: List of all edges in the graph.
        """
        return [ a for a in self.edge_properties.keys() ]

    def has_node(self, node):
        """
        Return whether the requested node exists.

        @type  node: node
        @param node: Node identifier

        @rtype:  boolean
        @return: Truth-value for node existence.
        """
        return node in self.node_neighbors


    def add_node(self, node, attrs=None):
        """
        Add given node to the graph.
        
        @attention: While nodes can be of any type, it's strongly recommended to use only
        numbers and single-line strings as node identifiers if you intend to use write().

        @type  node: node
        @param node: Node identifier.
        
        @type  attrs: list
        @param attrs: List of node attributes specified as (attribute, value) tuples.
        """
        if attrs is None:
            attrs = []
        if (not node in self.node_neighbors):
            self.node_neighbors[node] = []
            self.node_attr[node] = attrs
        else:
            raise AdditionError("Node %s already in graph" % node)

    def add_edge(self, edge, wt=1, label='', attrs=[]):
        """
        Add an edge to the graph connecting two nodes.
        
        An edge, here, is a pair of nodes like C{(n, m)}.

        @type  edge: tuple
        @param edge: Edge.

        @type  wt: number
        @param wt: Edge weight.
        
        @type  label: string
        @param label: Edge label.
        
        @type  attrs: list
        @param attrs: List of node attributes specified as (attribute, value) tuples.
        """
        u, v = edge
        if (v not in self.node_neighbors[u] and u not in self.node_neighbors[v]):
            self.node_neighbors[u].append(v)
            if (u != v):
                self.node_neighbors[v].append(u)
                
            self.add_edge_attributes((u,v), attrs)        
            self.set_edge_properties((u, v), label=label, weight=wt)
        else:
            raise AdditionError("Edge (%s, %s) already in graph" % (u, v))


    def del_node(self, node):
        """
        Remove a node from the graph.
        
        @type  node: node
        @param node: Node identifier.
        """
        for each in list(self.neighbors(node)):
            if (each != node):
                self.del_edge((each, node))
        del(self.node_neighbors[node])
        del(self.node_attr[node])


    def del_edge(self, edge):
        """
        Remove an edge from the graph.

        @type  edge: tuple
        @param edge: Edge.
        """
        u, v = edge
        self.node_neighbors[u].remove(v)
        self.del_edge_labeling((u, v))  
        if (u != v):
            self.node_neighbors[v].remove(u)
            self.del_edge_labeling((v, u)) # TODO: This is redundant

    def has_edge(self, edge):
        """
        Return whether an edge exists.

        @type  edge: tuple
        @param edge: Edge.

        @rtype:  boolean
        @return: Truth-value for edge existence.
        """
        u,v = edge
        return (u,v) in self.edge_properties and (v,u) in self.edge_properties
    
    
    def node_order(self, node):
        """
        Return the order of the graph
        
        @rtype:  number
        @return: Order of the given node.
        """
        return len(self.neighbors(node))


    def __eq__(self, other):
        """
        Return whether this graph is equal to another one.
        
        @type other: graph, digraph
        @param other: Other graph or digraph
        
        @rtype: boolean
        @return: Whether this graph and the other are equal.
        """
        return common.__eq__(self, other) and labeling.__eq__(self, other)
    
    def __ne__(self, other):
        """
        Return whether this graph is not equal to another one.
        
        @type other: graph, digraph
        @param other: Other graph or digraph
        
        @rtype: boolean
        @return: Whether this graph and the other are different.
        """
        return not (self == other)
