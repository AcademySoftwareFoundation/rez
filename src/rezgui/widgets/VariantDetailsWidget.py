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


from Qt import QtWidgets, QtGui
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.widgets.ViewGraphButton import ViewGraphButton
from rezgui.util import create_pane


class VariantDetailsWidget(QtWidgets.QWidget, ContextViewMixin):
    def __init__(self, context_model=None, parent=None):
        super(VariantDetailsWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)
        self.variant = None

        self.edit = StreamableTextEdit()
        self.edit.setStyleSheet("font: 9pt 'Courier'")
        self.view_graph_btn = ViewGraphButton(context_model)
        self._update_graph_btn_visibility()
        btn_pane = create_pane([None, self.view_graph_btn], True, compact=True)

        create_pane([self.edit, btn_pane], False, compact=True, parent_widget=self)
        self.clear()

    def clear(self):
        self.edit.clear()
        self.setEnabled(False)

    def set_variant(self, variant):
        if variant == self.variant:
            return

        if variant is None:
            self.clear()
        else:
            self.setEnabled(True)
            self.edit.clear()
            variant.print_info(self.edit, skip_attributes=("changelog",))
            self.edit.moveCursor(QtGui.QTextCursor.Start)
            self.view_graph_btn.set_variant(variant)

        self.variant = variant

    def _update_graph_btn_visibility(self):
        self.view_graph_btn.setVisible(bool(self.context()))

    def _contextChanged(self, flags=0):
        self._update_graph_btn_visibility()
