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
Search algorithms.

@sort: breadth_first_search, depth_first_search
"""


# Imports
from rez.vendor.pygraph.algorithms.filters.null import null
from sys import getrecursionlimit, setrecursionlimit


# Depth-first search

def depth_first_search(graph, root=None, filter=null()):
    """
    Depth-first search.

    @type  graph: graph, digraph
    @param graph: Graph.
    
    @type  root: node
    @param root: Optional root node (will explore only root's connected component)

    @rtype:  tuple
    @return: A tupple containing a dictionary and two lists:
        1. Generated spanning tree
        2. Graph's preordering
        3. Graph's postordering
    """
    
    recursionlimit = getrecursionlimit()
    setrecursionlimit(max(len(graph.nodes())*2,recursionlimit))

    def dfs(node):
        """
        Depth-first search subfunction.
        """
        visited[node] = 1
        pre.append(node)
        # Explore recursively the connected component
        for each in graph[node]:
            if (each not in visited and filter(each, node)):
                spanning_tree[each] = node
                dfs(each)
        post.append(node)

    visited = {}            # List for marking visited and non-visited nodes
    spanning_tree = {}      # Spanning tree
    pre = []                # Graph's preordering
    post = []               # Graph's postordering
    filter.configure(graph, spanning_tree)

    # DFS from one node only
    if (root is not None):
        if filter(root, None):
            spanning_tree[root] = None
            dfs(root)
        setrecursionlimit(recursionlimit)
        return spanning_tree, pre, post
    
    # Algorithm loop
    for each in graph:
        # Select a non-visited node
        if (each not in visited and filter(each, None)):
            spanning_tree[each] = None
            # Explore node's connected component
            dfs(each)

    setrecursionlimit(recursionlimit)
    
    return (spanning_tree, pre, post)


# Breadth-first search

def breadth_first_search(graph, root=None, filter=null()):
    """
    Breadth-first search.

    @type  graph: graph, digraph
    @param graph: Graph.

    @type  root: node
    @param root: Optional root node (will explore only root's connected component)

    @rtype:  tuple
    @return: A tuple containing a dictionary and a list.
        1. Generated spanning tree
        2. Graph's level-based ordering
    """

    def bfs():
        """
        Breadth-first search subfunction.
        """
        while (queue != []):
            node = queue.pop(0)
            
            for other in graph[node]:
                if (other not in spanning_tree and filter(other, node)):
                    queue.append(other)
                    ordering.append(other)
                    spanning_tree[other] = node
    
    queue = []            # Visiting queue
    spanning_tree = {}    # Spanning tree
    ordering = []
    filter.configure(graph, spanning_tree)
    
    # BFS from one node only
    if (root is not None):
        if filter(root, None):
            queue.append(root)
            ordering.append(root)
            spanning_tree[root] = None
            bfs()
        return spanning_tree, ordering

    # Algorithm
    for each in graph:
        if (each not in spanning_tree):
            if filter(each, None):
                queue.append(each)
                ordering.append(each)
                spanning_tree[each] = None
                bfs()

    return spanning_tree, ordering
