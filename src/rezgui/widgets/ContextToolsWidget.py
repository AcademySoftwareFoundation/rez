# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from Qt import QtCompat, QtCore, QtWidgets
from rezgui.widgets.ToolWidget import ToolWidget
from rezgui.models.ContextModel import ContextModel
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.util import get_icon
from rezgui.objects.App import app


class _TreeNode(QtWidgets.QLabel):

    clicked = QtCore.Signal()

    def __init__(self, item, txt, parent=None):
        super(_TreeNode, self).__init__(txt, parent)
        self.item = item
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        super(_TreeNode, self).mouseReleaseEvent(event)
        self.clicked.emit()
        if event.button() == QtCore.Qt.LeftButton:
            self.item.setExpanded(not self.item.isExpanded())


class ContextToolsWidget(QtWidgets.QTreeWidget, ContextViewMixin):

    toolsChanged = QtCore.Signal()

    def __init__(self, context_model=None, parent=None):
        super(ContextToolsWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

        self.tool_widgets = {}
        self.package_icon = get_icon("package", as_qicon=True)

        h = self.header()
        h.stretchLastSection()
        QtCompat.QHeaderView.setSectionResizeMode(
            h, QtWidgets.QHeaderView.Fixed)
        h.setVisible(False)

        self.setColumnCount(2)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        #app.process_tracker.instanceCountChanged.connect(self._instanceCountChanged)

        self.refresh()

    def num_tools(self):
        return len(self.tool_widgets)

    def refresh(self):
        self.clear()
        self.tool_widgets = {}
        context = self.context()
        if not context:
            return

        variants = (x for x in context.resolved_packages if x.tools)
        for variant in sorted(variants, key=lambda x: x.name):
            if not variant.tools:
                continue

            item = QtWidgets.QTreeWidgetItem(self)
            item.setIcon(0, self.package_icon)
            widget = _TreeNode(item, variant.qualified_package_name)
            widget.clicked.connect(self._clear_selection)
            self.setItemWidget(item, 1, widget)

            for tool in sorted(variant.tools):
                item_ = QtWidgets.QTreeWidgetItem(item)
                widget = ToolWidget(context, tool)  #, app.process_tracker)
                widget.clicked.connect(self._clear_selection)
                self.setItemWidget(item_, 1, widget)
                self.tool_widgets[tool] = widget

        self.resizeColumnToContents(0)
        self.toolsChanged.emit()

    def _contextChanged(self, flags=0):
        if not flags & (ContextModel.CONTEXT_CHANGED):
            return
        self.refresh()

    def _clear_selection(self):
        self.setCurrentIndex(QtCore.QModelIndex())
        self.clearSelection()

    def _instanceCountChanged(self, context_id, tool_name, num_procs):
        if self.context() is None or context_id != id(self.context()):
            return

        widget = self.tool_widgets.get(str(tool_name))
        if widget:
            widget.set_instance_count(num_procs)
