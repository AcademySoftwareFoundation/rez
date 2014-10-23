__author__ = 'federicon'
__docformat__ = 'epytext'

from rez.dot import view_graph

def view_graph_from_resolved_context(resolvedContext, dest_file=None):

    view_graph(resolvedContext.graph_string, dest_file=dest_file)