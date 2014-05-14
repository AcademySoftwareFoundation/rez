# Copyright (c) 2008-2009 Pedro Matiello <pmatiello@gmail.com>
#                         Zsolt Haraszti <zsolt@drawwell.net>
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
Random graph generators.

@sort: generate, generate_hypergraph
"""


# Imports
from rez.vendor.pygraph.classes.graph import graph
from rez.vendor.pygraph.classes.digraph import digraph
from rez.vendor.pygraph.classes.hypergraph import hypergraph
from random import randint, choice, shuffle #@UnusedImport
from time import time

# Generator

def generate(num_nodes, num_edges, directed=False, weight_range=(1, 1)):
    """
    Create a random graph.
    
    @type  num_nodes: number
    @param num_nodes: Number of nodes.
    
    @type  num_edges: number
    @param num_edges: Number of edges.
    
    @type  directed: bool
    @param directed: Whether the generated graph should be directed or not.  

    @type  weight_range: tuple
    @param weight_range: tuple of two integers as lower and upper limits on randomly generated
    weights (uniform distribution).
    """
    # Graph creation
    if directed:
        random_graph = digraph()
    else:
        random_graph = graph()

    # Nodes
    nodes = range(num_nodes)
    random_graph.add_nodes(nodes)
    
    # Build a list of all possible edges
    edges = []
    edges_append = edges.append
    for x in nodes:
        for y in nodes:
            if ((directed and x != y) or (x > y)):
                edges_append((x, y))
    
    # Randomize the list
    shuffle(edges)
    
    # Add edges to the graph
    min_wt = min(weight_range)
    max_wt = max(weight_range)
    for i in range(num_edges):
        each = edges[i]
        random_graph.add_edge((each[0], each[1]), wt = randint(min_wt, max_wt))

    return random_graph


def generate_hypergraph(num_nodes, num_edges, r = 0):
    """
    Create a random hyper graph.
    
    @type  num_nodes: number
    @param num_nodes: Number of nodes.
    
    @type  num_edges: number
    @param num_edges: Number of edges.
    
    @type  r: number
    @param r: Uniform edges of size r.
    """
    # Graph creation
    random_graph = hypergraph()
    
    # Nodes
    nodes = list(map(str, list(range(num_nodes))))
    random_graph.add_nodes(nodes)
    
    # Base edges
    edges = list(map(str, list(range(num_nodes, num_nodes+num_edges))))
    random_graph.add_hyperedges(edges)
    
    # Connect the edges
    if 0 == r:
        # Add each edge with 50/50 probability
        for e in edges:
            for n in nodes:
                if choice([True, False]):
                    random_graph.link(n, e)
    
    else:
        # Add only uniform edges
        for e in edges:
            # First shuffle the nodes
            shuffle(nodes)
            
            # Then take the first r nodes
            for i in range(r):
                random_graph.link(nodes[i], e)
    
    return random_graph
