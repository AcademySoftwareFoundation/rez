from rezgui.qt import QtGui
from rezgui.util import create_pane, get_icon_widget, update_font
from rez.resolved_context import PatchLock


class EffectivePackageCellWidget(QtGui.QWidget):
    def __init__(self, request, type_, parent=None):
        super(EffectivePackageCellWidget, self).__init__(parent)

        if type_ == "implicit":
            icon_name = "cog"
            tooltip = "implicit package"
        else:
            icon_name = type_
            tooltip = PatchLock[type_].description

        icon_widget = get_icon_widget(icon_name, tooltip)
        label = QtGui.QLabel(str(request))
        update_font(label, italic=True)

        create_pane([icon_widget, (label, 1)], True, parent_widget=self,
                    compact=True)
        self.setEnabled(False)  # this widget always disabled by design


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
