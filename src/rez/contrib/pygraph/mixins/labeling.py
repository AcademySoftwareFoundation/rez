# Copyright (c) 2008-2009 Pedro Matiello <pmatiello@gmail.com>
#                         Salim Fadhley <sal@stodge.org>
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


class labeling( object ):
    """
    Generic labeling support for graphs
    
    @sort: __eq__, __init__, add_edge_attribute, add_edge_attributes, add_node_attribute,
    del_edge_labeling, del_node_labeling, edge_attributes, edge_label, edge_weight,
    get_edge_properties, node_attributes, set_edge_label, set_edge_properties, set_edge_weight 
    """
    WEIGHT_ATTRIBUTE_NAME = "weight"
    DEFAULT_WEIGHT = 1
    
    LABEL_ATTRIBUTE_NAME = "label"
    DEFAULT_LABEL = ""
    
    def __init__(self):
        # Metadata bout edges
        self.edge_properties = {}    # Mapping: Edge -> Dict mapping, lablel-> str, wt->num
        self.edge_attr = {}          # Key value pairs: (Edge -> Attributes)
        
        # Metadata bout nodes
        self.node_attr = {}          # Pairing: Node -> Attributes
        
    def del_node_labeling( self, node ):
        if node in self.node_attr:
            # Since attributes and properties are lazy, they might not exist.
            del( self.node_attr[node] )
        
    def del_edge_labeling( self, edge ):
        
        keys = [edge]
        if not self.DIRECTED:
            keys.append(edge[::-1])
            
        for key in keys:
            for mapping in [self.edge_properties, self.edge_attr ]:
                try:
                    del ( mapping[key] )
                except KeyError:
                    pass
    
    def edge_weight(self, edge):
        """
        Get the weight of an edge.

        @type  edge: edge
        @param edge: One edge.
        
        @rtype:  number
        @return: Edge weight.
        """
        return self.get_edge_properties( edge ).setdefault( self.WEIGHT_ATTRIBUTE_NAME, self.DEFAULT_WEIGHT )


    def set_edge_weight(self, edge, wt):
        """
        Set the weight of an edge.

        @type  edge: edge
        @param edge: One edge.

        @type  wt: number
        @param wt: Edge weight.
        """
        self.set_edge_properties(edge, weight=wt )
        if not self.DIRECTED:
            self.set_edge_properties((edge[1], edge[0]) , weight=wt )


    def edge_label(self, edge):
        """
        Get the label of an edge.

        @type  edge: edge
        @param edge: One edge.
        
        @rtype:  string
        @return: Edge label
        """
        return self.get_edge_properties( edge ).setdefault( self.LABEL_ATTRIBUTE_NAME, self.DEFAULT_LABEL )

    def set_edge_label(self, edge, label):
        """
        Set the label of an edge.

        @type  edge: edge
        @param edge: One edge.

        @type  label: string
        @param label: Edge label.
        """
        self.set_edge_properties(edge, label=label )
        if not self.DIRECTED:
            self.set_edge_properties((edge[1], edge[0]) , label=label )
            
    def set_edge_properties(self, edge, **properties ):
        self.edge_properties.setdefault( edge, {} ).update( properties )
        if (not self.DIRECTED and edge[0] != edge[1]):
            self.edge_properties.setdefault((edge[1], edge[0]), {}).update( properties )
        
    def get_edge_properties(self, edge):
        return self.edge_properties.setdefault( edge, {} )
            
    def add_edge_attribute(self, edge, attr):
        """
        Add attribute to the given edge.

        @type  edge: edge
        @param edge: One edge.

        @type  attr: tuple
        @param attr: Node attribute specified as a tuple in the form (attribute, value).
        """
        self.edge_attr[edge] = self.edge_attributes(edge) + [attr]
        
        if (not self.DIRECTED and edge[0] != edge[1]):
            self.edge_attr[(edge[1],edge[0])] = self.edge_attributes((edge[1], edge[0])) + [attr]
    
    def add_edge_attributes(self, edge, attrs):
        """
        Append a sequence of attributes to the given edge
        
        @type  edge: edge
        @param edge: One edge.

        @type  attrs: tuple
        @param attrs: Node attributes specified as a sequence of tuples in the form (attribute, value).
        """
        for attr in attrs:
            self.add_edge_attribute(edge, attr)
    
    
    def add_node_attribute(self, node, attr):
        """
        Add attribute to the given node.

        @type  node: node
        @param node: Node identifier

        @type  attr: tuple
        @param attr: Node attribute specified as a tuple in the form (attribute, value).
        """
        self.node_attr[node] = self.node_attr[node] + [attr]


    def node_attributes(self, node):
        """
        Return the attributes of the given node.

        @type  node: node
        @param node: Node identifier

        @rtype:  list
        @return: List of attributes specified tuples in the form (attribute, value).
        """
        return self.node_attr[node]


    def edge_attributes(self, edge):
        """
        Return the attributes of the given edge.

        @type  edge: edge
        @param edge: One edge.

        @rtype:  list
        @return: List of attributes specified tuples in the form (attribute, value).
        """
        try:
            return self.edge_attr[edge]
        except KeyError:
            return []

    def __eq__(self, other):
        """
        Return whether this graph is equal to another one.
        
        @type other: graph, digraph
        @param other: Other graph or digraph
        
        @rtype: boolean
        @return: Whether this graph and the other are equal.
        """
        def attrs_eq(list1, list2):
            for each in list1:
                if (each not in list2): return False
            for each in list2:
                if (each not in list1): return False
            return True
        
        def edges_eq():
            for edge in self.edges():
                if (self.edge_weight(edge) != other.edge_weight(edge)): return False
                if (self.edge_label(edge) != other.edge_label(edge)): return False
                if (not attrs_eq(self.edge_attributes(edge), other.edge_attributes(edge))): return False 
            return True
        
        def nodes_eq():
            for node in self:
                if (not attrs_eq(self.node_attributes(node), other.node_attributes(node))): return False 
            return True
        
        return nodes_eq() and edges_eq()