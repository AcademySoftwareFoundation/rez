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


from Qt import QtCore, QtWidgets
from rezgui.objects.App import app
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.widgets.ToolWidget import ToolWidget


class VariantToolsList(QtWidgets.QTableWidget, ContextViewMixin):
    def __init__(self, context_model=None, parent=None):
        super(VariantToolsList, self).__init__(0, 1, parent)
        ContextViewMixin.__init__(self, context_model)

        self.variant = None
        self.tool_widgets = {}

        self.setGridStyle(QtCore.Qt.DotLine)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setVisible(False)
        vh = self.verticalHeader()
        vh.setVisible(False)

        #app.process_tracker.instanceCountChanged.connect(self._instanceCountChanged)

    def clear(self):
        self.tool_widgets = {}
        super(VariantToolsList, self).clear()
        self.setEnabled(False)

    def set_variant(self, variant):
        if variant == self.variant:
            return

        self.clear()

        if variant is not None:
            tools = sorted(variant.tools or [])
            self.setRowCount(len(tools))
            self.setEnabled(True)
            context = self.context()

            for i, tool in enumerate(tools):
                widget = ToolWidget(context, tool, app.process_tracker)
                widget.clicked.connect(self._clear_selection)
                self.setCellWidget(i, 0, widget)
                self.tool_widgets[tool] = widget

            select_mode = QtWidgets.QAbstractItemView.SingleSelection \
                if context else QtWidgets.QAbstractItemView.NoSelection
            self.setSelectionMode(select_mode)

        self.variant = variant

    def _clear_selection(self):
        self.clearSelection()
        self.setCurrentIndex(QtCore.QModelIndex())

    def _instanceCountChanged(self, context_id, tool_name, num_procs):
        if self.context() is None or context_id != id(self.context()):
            return

        widget = self.tool_widgets.get(str(tool_name))
        if widget:
            widget.set_instance_count(num_procs)
