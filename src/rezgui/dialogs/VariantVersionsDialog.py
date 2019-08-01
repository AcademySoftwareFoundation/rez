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
