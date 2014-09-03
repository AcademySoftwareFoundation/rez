from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, get_icon_widget, lock_types


class EffectivePackageCellWidget(QtGui.QWidget):
    types_ = lock_types.copy()
    types_["implicit"] = "implicit package"

    def __init__(self, request, type_, parent=None):
        super(EffectivePackageCellWidget, self).__init__(parent)

        tooltip = self.types_.get(type_)
        assert tooltip
        icon_widget = get_icon_widget(type_, tooltip)

        label = QtGui.QLabel(str(request))
        font = label.font()
        font.setItalic(True)
        label.setFont(font)

        create_pane([icon_widget, (label, 1)], True, parent_widget=self,
                    compact=True)
        self.setEnabled(False)  # this widget always disabled by design
