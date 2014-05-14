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
Cycle detection algorithms.

@sort: find_cycle
"""


# Imports
from rez.vendor.pygraph.classes.exceptions import InvalidGraphType
from rez.vendor.pygraph.classes.digraph import digraph as digraph_class
from rez.vendor.pygraph.classes.graph import graph as graph_class
from sys import getrecursionlimit, setrecursionlimit

def find_cycle(graph):
    """
    Find a cycle in the given graph.
    
    This function will return a list of nodes which form a cycle in the graph or an empty list if
    no cycle exists.
    
    @type graph: graph, digraph
    @param graph: Graph.
    
    @rtype: list
    @return: List of nodes. 
    """
    
    if (isinstance(graph, graph_class)):
        directed = False
    elif (isinstance(graph, digraph_class)):
        directed = True
    else:
        raise InvalidGraphType

    def find_cycle_to_ancestor(node, ancestor):
        """
        Find a cycle containing both node and ancestor.
        """
        path = []
        while (node != ancestor):
            if (node is None):
                return []
            path.append(node)
            node = spanning_tree[node]
        path.append(node)
        path.reverse()
        return path
    
    def dfs(node):
        """
        Depth-first search subfunction.
        """
        visited[node] = 1
        # Explore recursively the connected component
        for each in graph[node]:
            if (cycle):
                return
            if (each not in visited):
                spanning_tree[each] = node
                dfs(each)
            else:
                if (directed or spanning_tree[node] != each):
                    cycle.extend(find_cycle_to_ancestor(node, each))

    recursionlimit = getrecursionlimit()
    setrecursionlimit(max(len(graph.nodes())*2,recursionlimit))

    visited = {}              # List for marking visited and non-visited nodes
    spanning_tree = {}        # Spanning tree
    cycle = []

    # Algorithm outer-loop
    for each in graph:
        # Select a non-visited node
        if (each not in visited):
            spanning_tree[each] = None
            # Explore node's connected component
            dfs(each)
            if (cycle):
                setrecursionlimit(recursionlimit)
                return cycle

    setrecursionlimit(recursionlimit)
    return []
