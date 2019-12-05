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
