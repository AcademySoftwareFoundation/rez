# Copyright (c) 2008-2009 Pedro Matiello <pmatiello@gmail.com>
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
Radial search filter.
"""


class radius(object):
    """
    Radial search filter.
    
    This will keep searching contained inside a specified limit.
    """
    
    def __init__(self, radius):
        """
        Initialize the filter.
        
        @type  radius: number
        @param radius: Search radius.
        """
        self.graph = None
        self.spanning_tree = None
        self.radius = radius
        self.done = False
    
    def configure(self, graph, spanning_tree):
        """
        Configure the filter.
        
        @type  graph: graph
        @param graph: Graph.
        
        @type  spanning_tree: dictionary
        @param spanning_tree: Spanning tree.
        """
        self.graph = graph
        self.spanning_tree = spanning_tree
         
    def __call__(self, node, parent):
        """
        Decide if the given node should be included in the search process.
        
        @type  node: node
        @param node: Given node.
        
        @type  parent: node
        @param parent: Given node's parent in the spanning tree.
        
        @rtype: boolean
        @return: Whether the given node should be included in the search process. 
        """
        
        def cost_to_root(node):
            if (node is not None):
                return cost_to_parent(node, st[node]) + cost_to_root(st[node])
            else:
                return 0
        
        def cost_to_parent(node, parent):
            if (parent is not None):
                return gr.edge_weight((parent, node))
            else:
                return 0
        
        gr = self.graph
        st = self.spanning_tree
        
        cost =  cost_to_parent(node, parent) + cost_to_root(parent)
        
        if (cost <= self.radius):
            return True
        else:
            return False