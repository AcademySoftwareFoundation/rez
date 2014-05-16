# Copyright (c) 2009 Pedro Matiello <pmatiello@gmail.com>
#                    Tomaz Kovacic <tomaz.kovacic@gmail.com> 
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
Critical path algorithms and transitivity detection algorithm.

@sort: critical_path, transitive_edges
"""


# Imports
from rez.vendor.pygraph.algorithms.cycles import find_cycle
from rez.vendor.pygraph.algorithms.traversal import traversal
from rez.vendor.pygraph.algorithms.sorting import topological_sorting

def _intersection(A,B):
    """
    A simple function to find an intersection between two arrays. 
    
    @type A: List 
    @param A: First List
    
    @type B: List
    @param B: Second List
    
    @rtype: List
    @return: List of Intersections
    """
    intersection = []
    for i in A:
        if i in B:
            intersection.append(i)
    return intersection

def transitive_edges(graph):
    """
    Return a list of transitive edges.
    
    Example of transitivity within graphs: A -> B, B -> C, A ->  C
    in this case the transitive edge is: A -> C
    
    @attention: This function is only meaningful for directed acyclic graphs.
    
    @type graph: digraph
    @param graph: Digraph
    
    @rtype: List
    @return: List containing tuples with transitive edges (or an empty array if the digraph
        contains a cycle) 
    """
    #if the graph contains a cycle we return an empty array
    if not len(find_cycle(graph)) == 0:
        return []
    
    tranz_edges = [] # create an empty array that will contain all the tuples
    
    #run trough all the nodes in the graph
    for start in topological_sorting(graph):
        #find all the successors on the path for the current node
        successors = [] 
        for a in traversal(graph,start,'pre'):
            successors.append(a)
        del successors[0] #we need all the nodes in it's path except the start node itself
        
        for next in successors:
            #look for an intersection between all the neighbors of the 
            #given node and all the neighbors from the given successor
            intersect_array = _intersection(graph.neighbors(next), graph.neighbors(start) )
            for a in intersect_array:
                if graph.has_edge((start, a)):
                    ##check for the detected edge and append it to the returned array   
                    tranz_edges.append( (start,a) )      
    return tranz_edges # return the final array


def critical_path(graph):
    """
    Compute and return the critical path in an acyclic directed weighted graph.
    
    @attention: This function is only meaningful for directed weighted acyclic graphs
    
    @type graph: digraph 
    @param graph: Digraph
    
    @rtype: List
    @return: List containing all the nodes in the path (or an empty array if the graph
        contains a cycle)
    """
    #if the graph contains a cycle we return an empty array
    if not len(find_cycle(graph)) == 0:
        return []
    
    #this empty dictionary will contain a tuple for every single node
    #the tuple contains the information about the most costly predecessor 
    #of the given node and the cost of the path to this node
    #(predecessor, cost)
    node_tuples = {}
        
    topological_nodes = topological_sorting(graph)
    
    #all the tuples must be set to a default value for every node in the graph
    for node in topological_nodes: 
        node_tuples.update( {node :(None, 0)}  )
    
    #run trough all the nodes in a topological order
    for node in topological_nodes:
        predecessors =[]
        #we must check all the predecessors
        for pre in graph.incidents(node):
            max_pre = node_tuples[pre][1]
            predecessors.append( (pre, graph.edge_weight( (pre, node) ) + max_pre )   )
        
        max = 0; max_tuple = (None, 0)
        for i in predecessors:#look for the most costly predecessor
            if i[1] >= max:
                max = i[1]
                max_tuple = i
        #assign the maximum value to the given node in the node_tuples dictionary
        node_tuples[node] = max_tuple                 
    
    #find the critical node
    max = 0; critical_node = None
    for k,v in list(node_tuples.items()):
        if v[1] >= max:
            max= v[1]
            critical_node = k
            
    
    path = []
    #find the critical path with backtracking trought the dictionary
    def mid_critical_path(end):
        if node_tuples[end][0] != None:
            path.append(end)
            mid_critical_path(node_tuples[end][0])
        else:
            path.append(end)
    #call the recursive function
    mid_critical_path(critical_node)
    
    path.reverse()
    return path #return the array containing the critical path