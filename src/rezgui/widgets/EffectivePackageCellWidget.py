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
