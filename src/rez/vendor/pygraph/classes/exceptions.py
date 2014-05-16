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
Exceptions.
"""

# Graph errors

class GraphError(RuntimeError):
    """
    A base-class for the various kinds of errors that occur in the the python-graph class.
    """
    pass

class AdditionError(GraphError):
    """
    This error is raised when trying to add a node or edge already added to the graph or digraph.
    """
    pass

class NodeUnreachable(GraphError):
    """
    Goal could not be reached from start.
    """
    def __init__(self, start, goal):
        msg = "Node %s could not be reached from node %s" % ( repr(goal), repr(start) )
        InvalidGraphType.__init__(self, msg)
        self.start = start
        self.goal = goal

class InvalidGraphType(GraphError):
    """
    Invalid graph type.
    """
    pass

# Algorithm errors

class AlgorithmError(RuntimeError):
    """
    A base-class for the various kinds of errors that occur in the the 
    algorithms package.
    """
    pass

class NegativeWeightCycleError(AlgorithmError):
    """
    Algorithms like the Bellman-Ford algorithm can detect and raise an exception 
    when they encounter a negative weight cycle.
    
    @see: pygraph.algorithms.shortest_path_bellman_ford
    """
    pass
