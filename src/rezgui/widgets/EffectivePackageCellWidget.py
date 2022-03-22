# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from Qt import QtWidgets
from rezgui.util import create_pane, get_icon_widget, update_font
from rez.resolved_context import PatchLock


class EffectivePackageCellWidget(QtWidgets.QWidget):
    def __init__(self, request, type_, parent=None):
        super(EffectivePackageCellWidget, self).__init__(parent)

        if type_ == "implicit":
            icon_name = "cog"
            tooltip = "implicit package"
        else:
            icon_name = type_
            tooltip = PatchLock[type_].description

        icon_widget = get_icon_widget(icon_name, tooltip)
        label = QtWidgets.QLabel(str(request))
        update_font(label, italic=True)

        create_pane([icon_widget, (label, 1)], True, parent_widget=self,
                    compact=True)
        self.setEnabled(False)  # this widget always disabled by design
