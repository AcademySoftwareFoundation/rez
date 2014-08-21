from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, get_icon_widget
from rez.packages import iter_packages


class VariantCellWidget(QtGui.QWidget):
    def __init__(self, variant, settings=None, parent=None):
        super(VariantCellWidget, self).__init__(parent)
        self.settings = settings
        self.variant = variant
        self.icons = []  # 3-tuples: widget, name, tooltip

        label = QtGui.QLabel(self.variant.qualified_package_name)
        if self.variant.description:
            label.setToolTip(self.variant.description)

        self.layout = QtGui.QHBoxLayout()
        self.layout.setSpacing(2)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.addWidget(label, 1)
        self.setLayout(self.layout)

        self.refresh()

    def refresh(self):
        new_icons = []

        if self.variant.is_local:
            new_icons.append(("local", "package is local"))

        package_paths = self.settings.get("packages_path")
        if self.variant.search_path in package_paths:
            # test if variant is latest package
            latest_pkg = None
            try:
                it = iter_packages(name=self.variant.name, paths=package_paths)
                latest_pkg = sorted(it, key=lambda x: x.version)[-1]
            except:
                pass
            if latest_pkg and self.variant.version == latest_pkg.version:
                new_icons.append(("tick", "package is latest"))
        else:
            new_icons.append(("error", "package is not in the search path"))

        self.set_icons(new_icons)

    def set_icons(self, icons):
        current_icons = [tuple(x[1:]) for x in self.icons]
        if icons == current_icons:
            return

        for t in self.icons:
            widget = t[0]
            self.layout.removeWidget(widget)
            widget.setParent(None)
        self.icons = []

        for name, tooltip in icons:
            widget = get_icon_widget(name, tooltip)
            self.layout.addWidget(widget)
            self.icons.append((widget, name, tooltip))
