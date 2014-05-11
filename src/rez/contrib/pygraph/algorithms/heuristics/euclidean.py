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
A* heuristic for euclidean graphs.
"""


# Imports


class euclidean(object):
    """
    A* heuristic for Euclidean graphs.
    
    This heuristic has three requirements:
        1. All nodes should have the attribute 'position';
        2. The weight of all edges should be the euclidean distance between the nodes it links;
        3. The C{optimize()} method should be called before the heuristic search.
    
    A small example for clarification:
    
    >>> g = graph.graph()
    >>> g.add_nodes(['A','B','C'])
    >>> g.add_node_attribute('A', ('position',(0,0)))
    >>> g.add_node_attribute('B', ('position',(1,1)))
    >>> g.add_node_attribute('C', ('position',(0,2)))
    >>> g.add_edge('A','B', wt=2)
    >>> g.add_edge('B','C', wt=2)
    >>> g.add_edge('A','C', wt=4)
    >>> h = graph.heuristics.euclidean()
    >>> h.optimize(g)
    >>> g.heuristic_search('A', 'C', h)
    """
    
    def __init__(self):
        """
        Initialize the heuristic object.
        """
        self.distances = {}
        
    def optimize(self, graph):
        """
        Build a dictionary mapping each pair of nodes to a number (the distance between them).
        
        @type  graph: graph
        @param graph: Graph. 
        """
        for start in graph.nodes():
            for end in graph.nodes():
                for each in graph.node_attributes(start):
                    if (each[0] == 'position'):
                        start_attr = each[1]
                        break
                for each in graph.node_attributes(end):
                    if (each[0] == 'position'):
                        end_attr = each[1]
                        break
                dist = 0
                for i in range(len(start_attr)):
                    dist = dist + (float(start_attr[i]) - float(end_attr[i]))**2
                self.distances[(start,end)] = dist
        
    def __call__(self, start, end):
        """
        Estimate how far start is from end.
        
        @type  start: node
        @param start: Start node.
        
        @type  end: node
        @param end: End node.
        """
        assert len(list(self.distances.keys())) > 0, "You need to optimize this heuristic for your graph before it can be used to estimate."
                
        return self.distances[(start,end)]