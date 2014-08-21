from rezgui.qt import QtCore, QtGui
from rezgui.widgets.VariantVersionsTable import VariantVersionsTable
from rez.util import positional_number_string


class VariantVersionsWidget(QtGui.QWidget):
    def __init__(self, settings, parent=None):
        super(VariantVersionsWidget, self).__init__(parent)
        self.settings = settings
        self.variant = None

        self.label = QtGui.QLabel()
        self.table = VariantVersionsTable(settings)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.clear()

    def clear(self):
        self.label.setText("no package selected")
        self.table.clear()
        self.setEnabled(False)

    def refresh(self):
        variant = self.variant
        self.variant = None
        self.set_variant(variant)

    def set_variant(self, variant):
        self.table.set_variant(variant)

        if variant == self.variant:
            return

        package_paths = self.settings.get("packages_path")

        if variant is None:
            self.clear()
        else:
            if variant.search_path not in package_paths:
                self.clear()
                txt = "not on the package search path"
                self.label.setText(txt)
            else:
                self.setEnabled(True)
                n = self.table.version_index
                if n == 0:
                    txt = "the latest package"
                else:
                    nth = positional_number_string(n + 1)
                    txt = "the %s latest package" % nth

            txt = "%s is %s" % (variant.qualified_package_name, txt)
            self.label.setText(txt)

        self.variant = variant
