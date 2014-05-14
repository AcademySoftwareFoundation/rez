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


"""
Edmond Chow's heuristic for A*.
"""


# Imports
from rez.vendor.pygraph.algorithms.minmax import shortest_path 


class chow(object):
    """
    An implementation of the graph searching heuristic proposed by Edmond Chow.

    Remember to call the C{optimize()} method before the heuristic search.
    
    For details, check: U{http://www.edmondchow.com/pubs/levdiff-aaai.pdf}. 
    """
    
    def __init__(self, *centers):
        """
        Initialize a Chow heuristic object.
        """
        self.centers = centers
        self.nodes = {}
        
    def optimize(self, graph):
        """
        Build a dictionary mapping each pair of nodes to a number (the distance between them).
        
        @type  graph: graph
        @param graph: Graph. 
        """        
        for center in self.centers:
            shortest_routes = shortest_path(graph, center)[1]
            for node, weight in list(shortest_routes.items()):
                self.nodes.setdefault(node, []).append(weight)
        
    def __call__(self, start, end):
        """
        Estimate how far start is from end.
        
        @type  start: node
        @param start: Start node.
        
        @type  end: node
        @param end: End node.
        """
        assert len( list(self.nodes.keys()) ) > 0, "You need to optimize this heuristic for your graph before it can be used to estimate."
                
        cmp_sequence = list(zip( self.nodes[start], self.nodes[end] ))
        chow_number = max( abs( a-b ) for a,b in cmp_sequence )
        return chow_number
