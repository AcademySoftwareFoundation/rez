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
Traversal algorithms.

@sort: traversal
"""


# Minimal spanning tree

def traversal(graph, node, order):
    """
    Graph traversal iterator.

    @type  graph: graph, digraph
    @param graph: Graph.
    
    @type  node: node
    @param node: Node.
    
    @type  order: string
    @param order: traversal ordering. Possible values are:
        2. 'pre' - Preordering (default)
        1. 'post' - Postordering
    
    @rtype:  iterator
    @return: Traversal iterator.
    """
    visited = {}
    if (order == 'pre'):
        pre = 1
        post = 0
    elif (order == 'post'):
        pre = 0
        post = 1
    
    for each in _dfs(graph, visited, node, pre, post):
        yield each


def _dfs(graph, visited, node, pre, post):
    """
    Depth-first search subfunction for traversals.
    
    @type  graph: graph, digraph
    @param graph: Graph.

    @type  visited: dictionary
    @param visited: List of nodes (visited nodes are marked non-zero).

    @type  node: node
    @param node: Node to be explored by DFS.
    """
    visited[node] = 1
    if (pre): yield node
    # Explore recursively the connected component
    for each in graph[node]:
        if (each not in visited):
            for other in _dfs(graph, visited, each, pre, post):
                yield other
    if (post): yield node
