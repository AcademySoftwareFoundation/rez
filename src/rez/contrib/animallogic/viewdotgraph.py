__author__ = 'federicon'
__docformat__ = 'epytext'

from rez.utils.graph_utils import view_graph

def view_graph_from_resolved_context(resolvedContext, dest_file=None):
    view_graph(resolvedContext.graph(as_dot=True), dest_file=dest_file)
