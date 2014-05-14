# Copyright (c) 2008-2009 Pedro Matiello <pmatiello@gmail.com>
#                         Anand Jeyahar  <anand.jeyahar@gmail.com>
#                         Christian Muise <christian.muise@gmail.com>
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
Hypergraph class
"""


# Imports
from rez.vendor.pygraph.classes.graph import graph
from rez.vendor.pygraph.classes.exceptions import AdditionError

from rez.vendor.pygraph.mixins.labeling import labeling
from rez.vendor.pygraph.mixins.common import common
from rez.vendor.pygraph.mixins.basegraph import basegraph

class hypergraph (basegraph, common, labeling):
    """
    Hypergraph class.
    
    Hypergraphs are a generalization of graphs where an edge (called hyperedge) can connect more
    than two nodes.
    
    @sort: __init__, __len__, __str__, add_hyperedge, add_hyperedges, add_node, add_nodes,
    del_edge, has_node, has_edge, has_hyperedge, hyperedges, link, links, nodes, unlink
    """

    # Technically this isn't directed, but it gives us the right
    #  behaviour with the parent classes.
    DIRECTED = True

    def __init__(self):
        """
        Initialize a hypergraph.
        """
        common.__init__(self)
        labeling.__init__(self)
        self.node_links = {}    # Pairing: Node -> Hyperedge
        self.edge_links = {}     # Pairing: Hyperedge -> Node
        self.graph = graph()    # Ordinary graph


    def nodes(self):
        """
        Return node list.
        
        @rtype:  list
        @return: Node list.
        """
        return list(self.node_links.keys())


    def edges(self):
        """
        Return the hyperedge list.
        
        @rtype:  list
        @return: List of hyperedges in the graph.
        """
        return self.hyperedges()


    def hyperedges(self):
        """
        Return hyperedge list.

        @rtype:  list
        @return: List of hyperedges in the graph.
        """
        return list(self.edge_links.keys())
    
    
    def has_edge(self, hyperedge):
        """
        Return whether the requested node exists.

        @type  hyperedge: hyperedge
        @param hyperedge: Hyperedge identifier

        @rtype:  boolean
        @return: Truth-value for hyperedge existence.
        """
        return self.has_hyperedge(hyperedge)
    
    
    def has_hyperedge(self, hyperedge):
        """
        Return whether the requested node exists.

        @type  hyperedge: hyperedge
        @param hyperedge: Hyperedge identifier

        @rtype:  boolean
        @return: Truth-value for hyperedge existence.
        """
        return hyperedge in self.edge_links


    def links(self, obj):
        """
        Return all nodes connected by the given hyperedge or all hyperedges
        connected to the given hypernode.
        
        @type  obj: hyperedge
        @param obj: Object identifier.
        
        @rtype:  list
        @return: List of node objects linked to the given hyperedge.
        """
        if obj in self.edge_links:
            return self.edge_links[obj]
        else:
            return self.node_links[obj]
    
    
    def neighbors(self, obj):
        """
        Return all neighbors adjacent to the given node.
        
        @type  obj: node
        @param obj: Object identifier.
        
        @rtype:  list
        @return: List of all node objects adjacent to the given node.
        """
        neighbors = set([])
        
        for e in self.node_links[obj]:
            neighbors.update(set(self.edge_links[e]))
        
        return list(neighbors - set([obj]))


    def has_node(self, node):
        """
        Return whether the requested node exists.

        @type  node: node
        @param node: Node identifier

        @rtype:  boolean
        @return: Truth-value for node existence.
        """
        return node in self.node_links


    def add_node(self, node):
        """
        Add given node to the hypergraph.
        
        @attention: While nodes can be of any type, it's strongly recommended to use only numbers
        and single-line strings as node identifiers if you intend to use write().

        @type  node: node
        @param node: Node identifier.
        """
        if (not node in self.node_links):
            self.node_links[node] = []
            self.node_attr[node] = []
            self.graph.add_node((node,'n'))
        else:
            raise AdditionError("Node %s already in graph" % node)
    
    
    def del_node(self, node):
        """
        Delete a given node from the hypergraph.
        
        @type  node: node
        @param node: Node identifier.
        """
        if self.has_node(node):
            for e in self.node_links[node]:
                self.edge_links[e].remove(node)

            self.node_links.pop(node)
            self.graph.del_node((node,'n'))


    def add_edge(self, hyperedge):
        """
        Add given hyperedge to the hypergraph.
        
        @attention: While hyperedge-nodes can be of any type, it's strongly recommended to use only
        numbers and single-line strings as node identifiers if you intend to use write().
        
        @type  hyperedge: hyperedge
        @param hyperedge: Hyperedge identifier.
        """
        self.add_hyperedge(hyperedge)
    

    def add_hyperedge(self, hyperedge):
        """
        Add given hyperedge to the hypergraph.

        @attention: While hyperedge-nodes can be of any type, it's strongly recommended to use only
        numbers and single-line strings as node identifiers if you intend to use write().
        
        @type  hyperedge: hyperedge
        @param hyperedge: Hyperedge identifier.
        """
        if (not hyperedge in self.edge_links):
            self.edge_links[hyperedge] = []
            self.graph.add_node((hyperedge,'h'))


    def add_edges(self, edgelist):
        """
        Add given hyperedges to the hypergraph.

        @attention: While hyperedge-nodes can be of any type, it's strongly recommended to use only
        numbers and single-line strings as node identifiers if you intend to use write().
        
        @type  edgelist: list
        @param edgelist: List of hyperedge-nodes to be added to the graph.
        """
        self.add_hyperedges(edgelist)
            

    def add_hyperedges(self, edgelist):
        """
        Add given hyperedges to the hypergraph.

        @attention: While hyperedge-nodes can be of any type, it's strongly recommended to use only
        numbers and single-line strings as node identifiers if you intend to use write().
        
        @type  edgelist: list
        @param edgelist: List of hyperedge-nodes to be added to the graph.
        """
        for each in edgelist:
            self.add_hyperedge(each)

    
    def del_edge(self, hyperedge):
        """
        Delete the given hyperedge.
        
        @type  hyperedge: hyperedge
        @param hyperedge: Hyperedge identifier.
        """
        self.del_hyperedge(hyperedge)
        
        
    def del_hyperedge(self, hyperedge):
        """
        Delete the given hyperedge.
        
        @type  hyperedge: hyperedge
        @param hyperedge: Hyperedge identifier.
        """
        if (hyperedge in self.hyperedges()):
            for n in self.edge_links[hyperedge]:
                self.node_links[n].remove(hyperedge)

            del(self.edge_links[hyperedge])
            self.del_edge_labeling(hyperedge)
            self.graph.del_node((hyperedge,'h'))
            

    def link(self, node, hyperedge):
        """
        Link given node and hyperedge.

        @type  node: node
        @param node: Node.

        @type  hyperedge: node
        @param hyperedge: Hyperedge.
        """
        if (hyperedge not in self.node_links[node]):
            self.edge_links[hyperedge].append(node)
            self.node_links[node].append(hyperedge)
            self.graph.add_edge(((node,'n'), (hyperedge,'h')))
        else:
            raise AdditionError("Link (%s, %s) already in graph" % (node, hyperedge))


    def unlink(self, node, hyperedge):
        """
        Unlink given node and hyperedge.

        @type  node: node
        @param node: Node.

        @type  hyperedge: hyperedge
        @param hyperedge: Hyperedge.
        """
        self.node_links[node].remove(hyperedge)
        self.edge_links[hyperedge].remove(node)
        self.graph.del_edge(((node,'n'), (hyperedge,'h')))

    
    def rank(self):
        """
        Return the rank of the given hypergraph.
        
        @rtype:  int
        @return: Rank of graph.
        """
        max_rank = 0
        
        for each in self.hyperedges():
            if len(self.edge_links[each]) > max_rank:
                max_rank = len(self.edge_links[each])
                
        return max_rank

    def __eq__(self, other):
        """
        Return whether this hypergraph is equal to another one.
        
        @type other: hypergraph
        @param other: Other hypergraph
        
        @rtype: boolean
        @return: Whether this hypergraph and the other are equal.
        """
        def links_eq():
            for edge in self.edges():
                for link in self.links(edge):
                    if (link not in other.links(edge)): return False
            for edge in other.edges():
                for link in other.links(edge):
                    if (link not in self.links(edge)): return False
            return True
        
        return common.__eq__(self, other) and links_eq() and labeling.__eq__(self, other)
    
    def __ne__(self, other):
        """
        Return whether this hypergraph is not equal to another one.
        
        @type other: hypergraph
        @param other: Other hypergraph
        
        @rtype: boolean
        @return: Whether this hypergraph and the other are different.
        """
        return not (self == other)