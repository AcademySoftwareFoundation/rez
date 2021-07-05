from Qt import QtCore, QtWidgets
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
from rezgui.dialogs.WriteGraphDialog import view_graph
from rezgui.util import add_menu_action


class ViewGraphButton(QtWidgets.QToolButton, ContextViewMixin):
    def __init__(self, context_model=None, parent=None):
        super(ViewGraphButton, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

        # If not None, prunes the graph to this package
        self.package_name = None

        self.menu = QtWidgets.QMenu()
        self.action_1 = add_menu_action(self.menu, "View Resolve Graph...",
                                        self._view_resolve_graph, "graph")
        self.action_2 = add_menu_action(self.menu, "View Dependency Graph...",
                                        self._view_dependency_graph)

        self.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.setDefaultAction(self.action_1)
        self.setMenu(self.menu)

        self.refresh()

    def set_variant(self, variant=None):
        self.package_name = variant.name if variant else None

    def refresh(self):
        self._contextChanged(ContextModel.CONTEXT_CHANGED)

    def _contextChanged(self, flags=0):
        if not flags & ContextModel.CONTEXT_CHANGED:
            return

        enable_resolve = False
        enable_dependency = False
        context = self.context()
        if context:
            enable_resolve = context.has_graph
            enable_dependency = context.success

        self.action_1.setEnabled(enable_resolve)
        self.action_2.setEnabled(enable_dependency)
        self.setEnabled(enable_resolve or enable_dependency)

    def _view_resolve_graph(self):
        graph_str = self.context().graph(as_dot=True)
        view_graph(graph_str, self.window(), prune_to=self.package_name)

    def _view_dependency_graph(self):
        from rez.vendor.pygraph.readwrite.dot import write as write_dot
        graph = self.context().get_dependency_graph()
        graph_str = write_dot(graph)
        view_graph(graph_str, self.window(), prune_to=self.package_name)


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
