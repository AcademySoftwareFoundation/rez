from rezgui.qt import QtCore, QtGui
from rezgui.widgets.VariantVersionsWidget import VariantVersionsWidget
from rezgui.dialogs.ConfiguredDialog import ConfiguredDialog
from rezgui.objects.App import app


class VariantVersionsDialog(ConfiguredDialog):
    def __init__(self, settings, variant, parent=None):
        super(VariantVersionsDialog, self).__init__(app.config,
                                                    "layout/window/package_versions",
                                                    parent)
        self.setWindowTitle("Package Versions")
        self.versions_widget = VariantVersionsWidget(settings, in_window=True)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.versions_widget)
        self.setLayout(layout)

        self.versions_widget.set_variant(variant)
        self.versions_widget.closeWindow.connect(self.close)
