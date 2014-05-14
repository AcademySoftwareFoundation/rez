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
Accessibility algorithms.

@sort: accessibility, connected_components, cut_edges, cut_nodes, mutual_accessibility
"""


# Imports
from sys import getrecursionlimit, setrecursionlimit

# Transitive-closure

def accessibility(graph):
    """
    Accessibility matrix (transitive closure).

    @type  graph: graph, digraph, hypergraph
    @param graph: Graph.

    @rtype:  dictionary
    @return: Accessibility information for each node.
    """
    recursionlimit = getrecursionlimit()
    setrecursionlimit(max(len(graph.nodes())*2,recursionlimit))
    
    accessibility = {}        # Accessibility matrix

    # For each node i, mark each node j if that exists a path from i to j.
    for each in graph:
        access = {}
        # Perform DFS to explore all reachable nodes
        _dfs(graph, access, 1, each)
        accessibility[each] = list(access.keys())
    
    setrecursionlimit(recursionlimit)
    return accessibility


# Strongly connected components

def mutual_accessibility(graph):
    """
    Mutual-accessibility matrix (strongly connected components).

    @type  graph: graph, digraph
    @param graph: Graph.

    @rtype:  dictionary
    @return: Mutual-accessibility information for each node.
    """
    recursionlimit = getrecursionlimit()
    setrecursionlimit(max(len(graph.nodes())*2,recursionlimit))
    
    mutual_access = {}
    stack = []
    low = {}
        
    def visit(node):
        if node in low:
            return

        num = len(low)
        low[node] = num
        stack_pos = len(stack)
        stack.append(node)
        
        for successor in graph.neighbors(node):
            visit(successor)
            low[node] = min(low[node], low[successor])
        
        if num == low[node]:
            component = stack[stack_pos:]
            del stack[stack_pos:]
            component.sort()
            for each in component:
                mutual_access[each] = component

            for item in component:
                low[item] = len(graph)
    
    for node in graph:
        visit(node)
    
    setrecursionlimit(recursionlimit)
    return mutual_access


# Connected components

def connected_components(graph):
    """
    Connected components.

    @type  graph: graph, hypergraph
    @param graph: Graph.

    @rtype:  dictionary
    @return: Pairing that associates each node to its connected component.
    """
    recursionlimit = getrecursionlimit()
    setrecursionlimit(max(len(graph.nodes())*2,recursionlimit))
    
    visited = {}
    count = 1

    # For 'each' node not found to belong to a connected component, find its connected
    # component.
    for each in graph:
        if (each not in visited):
            _dfs(graph, visited, count, each)
            count = count + 1
    
    setrecursionlimit(recursionlimit)
    return visited


# Limited DFS implementations used by algorithms here

def _dfs(graph, visited, count, node):
    """
    Depth-first search subfunction adapted for accessibility algorithms.
    
    @type  graph: graph, digraph, hypergraph
    @param graph: Graph.

    @type  visited: dictionary
    @param visited: List of nodes (visited nodes are marked non-zero).

    @type  count: number
    @param count: Counter of connected components.

    @type  node: node
    @param node: Node to be explored by DFS.
    """
    visited[node] = count
    # Explore recursively the connected component
    for each in graph[node]:
        if (each not in visited):
            _dfs(graph, visited, count, each)


# Cut-Edge and Cut-Vertex identification

# This works by creating a spanning tree for the graph and keeping track of the preorder number
# of each node in the graph in pre[]. The low[] number for each node tracks the pre[] number of
# the node with lowest pre[] number reachable from the first node.
#
# An edge (u, v) will be a cut-edge low[u] == pre[v]. Suppose v under the spanning subtree with
# root u. This means that, from u, through a path inside this subtree, followed by an backarc,
# one can not get out the subtree. So, (u, v) is the only connection between this subtree and
# the remaining parts of the graph and, when removed, will increase the number of connected
# components.

# Similarly, a node u will be a cut node if any of the nodes v in the spanning subtree rooted in
# u are so that low[v] > pre[u], which means that there's no path from v to outside this subtree
# without passing through u.

def cut_edges(graph):
    """
    Return the cut-edges of the given graph.
    
    A cut edge, or bridge, is an edge of a graph whose removal increases the number of connected
    components in the graph.
    
    @type  graph: graph, hypergraph
    @param graph: Graph.
    
    @rtype:  list
    @return: List of cut-edges.
    """
    recursionlimit = getrecursionlimit()
    setrecursionlimit(max(len(graph.nodes())*2,recursionlimit))

    # Dispatch if we have a hypergraph
    if 'hypergraph' == graph.__class__.__name__:
        return _cut_hyperedges(graph)

    pre = {}    # Pre-ordering
    low = {}    # Lowest pre[] reachable from this node going down the spanning tree + one backedge
    spanning_tree = {}
    reply = []
    pre[None] = 0

    for each in graph:
        if (each not in pre):
            spanning_tree[each] = None
            _cut_dfs(graph, spanning_tree, pre, low, reply, each)
    
    setrecursionlimit(recursionlimit)
    return reply


def _cut_hyperedges(hypergraph):
    """
    Return the cut-hyperedges of the given hypergraph.
    
    @type  hypergraph: hypergraph
    @param hypergraph: Hypergraph
    
    @rtype:  list
    @return: List of cut-nodes.
    """
    edges_ = cut_nodes(hypergraph.graph)
    edges = []
    
    for each in edges_:
        if (each[1] == 'h'):
            edges.append(each[0])
    
    return edges


def cut_nodes(graph):
    """
    Return the cut-nodes of the given graph.
    
    A cut node, or articulation point, is a node of a graph whose removal increases the number of
    connected components in the graph.
    
    @type  graph: graph, hypergraph
    @param graph: Graph.
        
    @rtype:  list
    @return: List of cut-nodes.
    """
    recursionlimit = getrecursionlimit()
    setrecursionlimit(max(len(graph.nodes())*2,recursionlimit))
    
    # Dispatch if we have a hypergraph
    if 'hypergraph' == graph.__class__.__name__:
        return _cut_hypernodes(graph)
        
    pre = {}    # Pre-ordering
    low = {}    # Lowest pre[] reachable from this node going down the spanning tree + one backedge
    reply = {}
    spanning_tree = {}
    pre[None] = 0
    
    # Create spanning trees, calculate pre[], low[]
    for each in graph:
        if (each not in pre):
            spanning_tree[each] = None
            _cut_dfs(graph, spanning_tree, pre, low, [], each)

    # Find cuts
    for each in graph:
        # If node is not a root
        if (spanning_tree[each] is not None):
            for other in graph[each]:
                # If there is no back-edge from descendent to a ancestral of each
                if (low[other] >= pre[each] and spanning_tree[other] == each):
                    reply[each] = 1
        # If node is a root
        else:
            children = 0
            for other in graph:
                if (spanning_tree[other] == each):
                    children = children + 1
            # root is cut-vertex iff it has two or more children
            if (children >= 2):
                reply[each] = 1

    setrecursionlimit(recursionlimit)
    return list(reply.keys())


def _cut_hypernodes(hypergraph):
    """
    Return the cut-nodes of the given hypergraph.
    
    @type  hypergraph: hypergraph
    @param hypergraph: Hypergraph
    
    @rtype:  list
    @return: List of cut-nodes.
    """
    nodes_ = cut_nodes(hypergraph.graph)
    nodes = []
    
    for each in nodes_:
        if (each[1] == 'n'):
            nodes.append(each[0])
    
    return nodes


def _cut_dfs(graph, spanning_tree, pre, low, reply, node):
    """
    Depth first search adapted for identification of cut-edges and cut-nodes.
    
    @type  graph: graph, digraph
    @param graph: Graph
    
    @type  spanning_tree: dictionary
    @param spanning_tree: Spanning tree being built for the graph by DFS.

    @type  pre: dictionary
    @param pre: Graph's preordering.
    
    @type  low: dictionary
    @param low: Associates to each node, the preordering index of the node of lowest preordering
    accessible from the given node.

    @type  reply: list
    @param reply: List of cut-edges.
    
    @type  node: node
    @param node: Node to be explored by DFS.
    """
    pre[node] = pre[None]
    low[node] = pre[None]
    pre[None] = pre[None] + 1
    
    for each in graph[node]:
        if (each not in pre):
            spanning_tree[each] = node
            _cut_dfs(graph, spanning_tree, pre, low, reply, each)
            if (low[node] > low[each]):
                low[node] = low[each]
            if (low[each] == pre[each]):
                reply.append((node, each))
        elif (low[node] > pre[each] and spanning_tree[node] != each):
            low[node] = pre[each]
