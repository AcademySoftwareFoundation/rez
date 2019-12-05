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
