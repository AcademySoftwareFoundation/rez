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
from rezgui.util import create_pane
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin
from rezgui.widgets.BrowsePackageWidget import BrowsePackageWidget
from rezgui.objects.App import app


class BrowsePackageDialog(QtWidgets.QDialog, StoreSizeMixin):
    def __init__(self, context_model, package_text=None, parent=None,
                 close_only=False, lock_package=False,
                 package_selectable_callback=None):
        config_key = "layout/window/browse_package"
        super(BrowsePackageDialog, self).__init__(parent)
        StoreSizeMixin.__init__(self, app.config, config_key)

        self.setWindowTitle("Find Package")
        self.package = None

        self.widget = BrowsePackageWidget(
            context_model, self, lock_package=lock_package,
            package_selectable_callback=package_selectable_callback)

        self.ok_btn = QtWidgets.QPushButton("Ok")
        buttons = [self.ok_btn]

        if close_only:
            close_btn = QtWidgets.QPushButton("Close")
            buttons.insert(0, close_btn)
            close_btn.clicked.connect(self.close)
            self.ok_btn.hide()
        else:
            cancel_btn = QtWidgets.QPushButton("Cancel")
            cancel_btn.clicked.connect(self.close)
            buttons.insert(0, cancel_btn)
            self.ok_btn.setEnabled(False)

        btn_pane = create_pane([None] + buttons, True)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.widget)
        layout.addWidget(btn_pane)
        self.setLayout(layout)

        self.ok_btn.clicked.connect(self._ok)
        self.widget.packageSelected.connect(self._set_package)
        self.widget.set_package_text(package_text)

    def _set_package(self):
        package = self.widget.current_package()
        if package is None:
            self.setWindowTitle("Find Package")
            self.ok_btn.setEnabled(False)
        else:
            self.setWindowTitle("Find Package - %s" % package.qualified_name)
            self.ok_btn.setEnabled(True)

    def _ok(self):
        self.package = self.widget.current_package()
        self.close()
