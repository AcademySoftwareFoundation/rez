# Copyright (c) 2007-2009 Pedro Matiello <pmatiello@gmail.com>
#                         Peter Sagerson <peter.sagerson@gmail.com>
#                         Johannes Reinhardt <jreinhardt@ist-dein-freund.de>
#                         Rhys Ulerich <rhys.ulerich@gmail.com>
#                         Roy Smith <roy@panix.com>
#                         Salim Fadhley <sal@stodge.org>
#                         Tomaz Kovacic <tomaz.kovacic@gmail.com>
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
Minimization and maximization algorithms.

@sort: heuristic_search, minimal_spanning_tree, shortest_path,
shortest_path_bellman_ford
"""

from rez.vendor.pygraph.algorithms.utils import heappush, heappop
from rez.vendor.pygraph.classes.exceptions import NodeUnreachable
from rez.vendor.pygraph.classes.exceptions import NegativeWeightCycleError
from rez.vendor.pygraph.classes.digraph import digraph
import bisect

# Minimal spanning tree

def minimal_spanning_tree(graph, root=None):
    """
    Minimal spanning tree.

    @attention: Minimal spanning tree is meaningful only for weighted graphs.

    @type  graph: graph
    @param graph: Graph.
    
    @type  root: node
    @param root: Optional root node (will explore only root's connected component)

    @rtype:  dictionary
    @return: Generated spanning tree.
    """
    visited = []            # List for marking visited and non-visited nodes
    spanning_tree = {}        # MInimal Spanning tree

    # Initialization
    if (root is not None):
        visited.append(root)
        nroot = root
        spanning_tree[root] = None
    else:
        nroot = 1
    
    # Algorithm loop
    while (nroot is not None):
        ledge = _lightest_edge(graph, visited)
        if (ledge == None):
            if (root is not None):
                break
            nroot = _first_unvisited(graph, visited)
            if (nroot is not None):
                spanning_tree[nroot] = None
            visited.append(nroot)
        else:
            spanning_tree[ledge[1]] = ledge[0]
            visited.append(ledge[1])

    return spanning_tree


def _first_unvisited(graph, visited):
    """
    Return first unvisited node.
    
    @type  graph: graph
    @param graph: Graph.

    @type  visited: list
    @param visited: List of nodes.
    
    @rtype:  node
    @return: First unvisited node.
    """
    for each in graph:
        if (each not in visited):
            return each
    return None


def _lightest_edge(graph, visited):
    """
    Return the lightest edge in graph going from a visited node to an unvisited one.
    
    @type  graph: graph
    @param graph: Graph.

    @type  visited: list
    @param visited: List of nodes.

    @rtype:  tuple
    @return: Lightest edge in graph going from a visited node to an unvisited one.
    """
    lightest_edge = None
    weight = None
    for each in visited:
        for other in graph[each]:
            if (other not in visited):
                w = graph.edge_weight((each, other))
                if (weight is None or w < weight or weight < 0):
                    lightest_edge = (each, other)
                    weight = w
    return lightest_edge


# Shortest Path

def shortest_path(graph, source):
    """
    Return the shortest path distance between source and all other nodes using Dijkstra's
    algorithm.
    
    @attention: All weights must be nonnegative.
    
    @see: shortest_path_bellman_ford

    @type  graph: graph, digraph
    @param graph: Graph.

    @type  source: node
    @param source: Node from which to start the search.

    @rtype:  tuple
    @return: A tuple containing two dictionaries, each keyed by target nodes.
        1. Shortest path spanning tree
        2. Shortest distance from given source to each target node
    Inaccessible target nodes do not appear in either dictionary.
    """
    # Initialization
    dist     = {source: 0}
    previous = {source: None}

    # This is a sorted queue of (dist, node) 2-tuples. The first item in the
    # queue is always either a finalized node that we can ignore or the node
    # with the smallest estimated distance from the source. Note that we will
    # not remove nodes from this list as they are finalized; we just ignore them
    # when they come up.
    q = [(0, source)]

    # The set of nodes for which we have final distances.
    finished = set()

    # Algorithm loop
    while len(q) > 0:
        du, u = q.pop(0)

        # Process reachable, remaining nodes from u
        if u not in finished:
            finished.add(u)
            for v in graph[u]:
                if v not in finished:
                    alt = du + graph.edge_weight((u, v))
                    if (v not in dist) or (alt < dist[v]):
                        dist[v] = alt
                        previous[v] = u
                        bisect.insort(q, (alt, v))

    return previous, dist



def shortest_path_bellman_ford(graph, source):
    """
    Return the shortest path distance between the source node and all other 
    nodes in the graph using Bellman-Ford's algorithm.
    
    This algorithm is useful when you have a weighted (and obviously 
    a directed) graph with negative weights.
    
    @attention: The algorithm can detect negative weight cycles and will raise 
    an exception. It's meaningful only for directed weighted graphs.
    
    @see: shortest_path
    
    @type graph: digraph
    @param graph: Digraph
    
    @type source: node
    @param source: Source node of the graph
    
    @raise NegativeWeightCycleError: raises if it finds a negative weight cycle.
    If this condition is met d(v) > d(u) + W(u, v) then raise the error. 
    
    @rtype: tuple 
    @return: A tuple containing two dictionaries, each keyed by target nodes.
    (same as shortest_path function that implements Dijkstra's algorithm)
        1. Shortest path spanning tree
        2. Shortest distance from given source to each target node
    """
    # initialize the required data structures       
    distance = {source : 0}
    predecessor = {source : None}
    
    # iterate and relax edges    
    for i in range(1,graph.order()-1):
        for src,dst in graph.edges():
            if (src in distance) and (dst not in distance):
                distance[dst] = distance[src] + graph.edge_weight((src,dst))
                predecessor[dst] = src
            elif (src  in distance) and (dst in distance) and \
            distance[src] + graph.edge_weight((src,dst)) < distance[dst]:
                distance[dst] = distance[src] + graph.edge_weight((src,dst))
                predecessor[dst] = src
                
    # detect negative weight cycles
    for src,dst in graph.edges():
        if src in distance and \
           dst in distance and \
           distance[src] + graph.edge_weight((src,dst)) < distance[dst]:
            raise NegativeWeightCycleError("Detected a negative weight cycle on edge (%s, %s)" % (src,dst))
        
    return predecessor, distance
        
#Heuristics search

def heuristic_search(graph, start, goal, heuristic):
    """
    A* search algorithm.
    
    A set of heuristics is available under C{graph.algorithms.heuristics}. User-created heuristics
    are allowed too.
    
    @type graph: graph, digraph
    @param graph: Graph
    
    @type start: node
    @param start: Start node
    
    @type goal: node
    @param goal: Goal node
    
    @type heuristic: function
    @param heuristic: Heuristic function
    
    @rtype: list
    @return: Optimized path from start to goal node 
    """
    
    # The queue stores priority, node, cost to reach, and parent.
    queue = [ (0, start, 0, None) ]

    # This dictionary maps queued nodes to distance of discovered paths
    # and the computed heuristics to goal. We avoid to compute the heuristics
    # more than once and to insert too many times the node in the queue.
    g = {}

    # This maps explored nodes to parent closest to the start
    explored = {}
    
    while queue:
        _, current, dist, parent = heappop(queue)
        
        if current == goal:
            path = [current] + [ n for n in _reconstruct_path( parent, explored ) ]
            path.reverse()
            return path

        if current in explored:
            continue

        explored[current] = parent

        for neighbor in graph[current]:
            if neighbor in explored:
                continue
            
            ncost = dist + graph.edge_weight((current, neighbor))

            if neighbor in g:
                qcost, h = g[neighbor]
                if qcost <= ncost:
                    continue
                # if ncost < qcost, a longer path to neighbor remains
                # g. Removing it would need to filter the whole
                # queue, it's better just to leave it there and ignore
                # it when we visit the node a second time.
            else:
                h = heuristic(neighbor, goal)
            
            g[neighbor] = ncost, h
            heappush(queue, (ncost + h, neighbor, ncost, current))

    raise NodeUnreachable( start, goal )

def _reconstruct_path(node, parents):
    while node is not None:
        yield node
        node = parents[node]

#maximum flow/minimum cut

def maximum_flow(graph, source, sink, caps = None):
    """
    Find a maximum flow and minimum cut of a directed graph by the Edmonds-Karp algorithm.

    @type graph: digraph
    @param graph: Graph

    @type source: node
    @param source: Source of the flow

    @type sink: node
    @param sink: Sink of the flow

    @type caps: dictionary
    @param caps: Dictionary specifying a maximum capacity for each edge. If not given, the weight of the edge
    will be used as its capacity. Otherwise, for each edge (a,b), caps[(a,b)] should be given.
    
    @rtype: tuple
    @return: A tuple containing two dictionaries
        1. contains the flow through each edge for a maximal flow through the graph
        2. contains to which component of a minimum cut each node belongs
    """

    #handle optional argument, if weights are available, use them, if not, assume one
    if caps == None:
        caps = {}
        for edge in graph.edges():
            caps[edge] = graph.edge_weight((edge[0],edge[1]))    
    
    #data structures to maintain
    f = {}.fromkeys(graph.edges(),0)    
    label = {}.fromkeys(graph.nodes(),[])
    label[source] = ['-',float('Inf')]
    u = {}.fromkeys(graph.nodes(),False)
    d = {}.fromkeys(graph.nodes(),float('Inf'))
    #queue for labelling
    q = [source]

    finished = False
    while not finished:
        #choose first labelled vertex with u == false
        for i in range(len(q)):
            if not u[q[i]]:
                v = q.pop(i)
                break

        #find augmenting path
        for w in graph.neighbors(v):
            if label[w] == [] and f[(v,w)] < caps[(v,w)]:
                d[w] = min(caps[(v,w)] - f[(v,w)],d[v])
                label[w] = [v,'+',d[w]]
                q.append(w)
        for w in graph.incidents(v):
            if label[w] == [] and f[(w,v)] > 0:
                d[w] = min(f[(w,v)],d[v])
                label[w] = [v,'-',d[w]]
                q.append(w)

        u[v] = True

        #extend flow by augmenting path        
        if label[sink] != []:
            delta = label[sink][-1]
            w = sink
            while w != source:
                v = label[w][0]
                if label[w][1] == '-':
                    f[(w,v)] = f[(w,v)] - delta
                else:
                    f[(v,w)] = f[(v,w)] + delta
                w = v
            #reset labels
            label = {}.fromkeys(graph.nodes(),[])
            label[source] = ['-',float('Inf')]
            q = [source]
            u = {}.fromkeys(graph.nodes(),False)
            d = {}.fromkeys(graph.nodes(),float('Inf'))

        #check whether finished
        finished = True
        for node in graph.nodes():
            if label[node] != [] and u[node] == False:
                finished = False

    #find the two components of the cut
    cut = {}
    for node in graph.nodes():
        if label[node] == []:
            cut[node] = 1
        else:
            cut[node] = 0
    return (f,cut)

def cut_value(graph, flow, cut):
    """
    Calculate the value of a cut.

    @type graph: digraph
    @param graph: Graph

    @type flow: dictionary
    @param flow: Dictionary containing a flow for each edge.

    @type cut: dictionary
    @param cut: Dictionary mapping each node to a subset index. The function only considers the flow between
    nodes with 0 and 1.
    
    @rtype: float
    @return: The value of the flow between the subsets 0 and 1
    """
    #max flow/min cut value calculation
    S = []
    T = []
    for node in cut.keys():
        if cut[node] == 0:
            S.append(node)
        elif cut[node] == 1:
            T.append(node)
    value = 0
    for node in S:
        for neigh in graph.neighbors(node):
            if neigh in T:
                value = value + flow[(node,neigh)]
        for inc in graph.incidents(node):
            if inc in T:
                value = value - flow[(inc,node)]    
    return value

def cut_tree(igraph, caps = None):
    """
    Construct a Gomory-Hu cut tree by applying the algorithm of Gusfield.

    @type igraph: graph
    @param igraph: Graph

    @type caps: dictionary
    @param caps: Dictionary specifying a maximum capacity for each edge. If not given, the weight of the edge
    will be used as its capacity. Otherwise, for each edge (a,b), caps[(a,b)] should be given.
    
    @rtype: dictionary
    @return: Gomory-Hu cut tree as a dictionary, where each edge is associated with its weight
    """

    #maximum flow needs a digraph, we get a graph
    #I think this conversion relies on implementation details outside the api and may break in the future
    graph = digraph()
    graph.add_graph(igraph)

    #handle optional argument
    if not caps:
        caps = {}
        for edge in graph.edges():
            caps[edge] = igraph.edge_weight(edge)

    #temporary flow variable
    f = {}

    #we use a numbering of the nodes for easier handling
    n = {}
    N = 0
    for node in graph.nodes():
        n[N] = node
        N = N + 1

    #predecessor function
    p = {}.fromkeys(range(N),0)
    p[0] = None

    for s in range(1,N):
        t = p[s]
        S = []
        #max flow calculation
        (flow,cut) = maximum_flow(graph,n[s],n[t],caps)
        for i in range(N):
            if cut[n[i]] == 0:
                S.append(i)
        
        value = cut_value(graph,flow,cut)

        f[s] = value

        for i in range(N):
            if i == s:
                continue
            if i in S and p[i] == t:
                p[i] = s
        if p[t] in S:
            p[s] = p[t]
            p[t] = s
            f[s] = f[t]
            f[t] = value

    #cut tree is a dictionary, where each edge is associated with its weight
    b = {}
    for i in range(1,N):
        b[(n[i],n[p[i]])] = f[i]
    return b

