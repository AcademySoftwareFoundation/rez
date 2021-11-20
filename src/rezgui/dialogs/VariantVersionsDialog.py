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
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin
from rezgui.widgets.VariantVersionsWidget import VariantVersionsWidget
from rezgui.objects.App import app


class VariantVersionsDialog(QtWidgets.QDialog, StoreSizeMixin):
    def __init__(self, context_model, variant, reference_variant=None, parent=None):
        config_key = "layout/window/package_versions"
        super(VariantVersionsDialog, self).__init__(parent)
        StoreSizeMixin.__init__(self, app.config, config_key)

        self.setWindowTitle("Package Versions")
        self.versions_widget = VariantVersionsWidget(
            context_model, reference_variant=reference_variant, in_window=True)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.versions_widget)
        self.setLayout(layout)

        self.versions_widget.set_variant(variant)
        self.versions_widget.closeWindow.connect(self.close)
