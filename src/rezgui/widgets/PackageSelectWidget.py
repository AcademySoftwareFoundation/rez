from rezgui.qt import QtCore, QtGui
from rezgui.widgets.PackageLineEdit import PackageLineEdit
from rezgui.widgets.IconButton import IconButton


class PackageSelectWidget(QtGui.QWidget):

    focusOutViaKeyPress = QtCore.Signal(str)
    focusOut = QtCore.Signal(str)
    textChanged = QtCore.Signal(str)

    def __init__(self, settings=None, parent=None):
        super(PackageSelectWidget, self).__init__(parent)
        self.settings = settings

        self.edit = PackageLineEdit(settings, self)
        self.edit.setStyleSheet("QLineEdit { border : 0px;}")
        self.btn = IconButton("round_plus")
        self.btn.hide()

        layout = QtGui.QHBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.btn)
        self.setLayout(layout)

        self.edit.focusIn.connect(self._focusIn)
        self.edit.focusOut.connect(self._focusOut)
        self.edit.focusOutViaKeyPress.connect(self._focusOutViaKeyPress)
        self.edit.textChanged.connect(self._textChanged)

    def text(self):
        return self.edit.text()

    def setText(self, txt):
        self.edit.setText(txt)

    def refresh(self):
        self.edit.refresh()

    def setCurrent(self):
        self.edit.setFocus()
        self.btn.show()

    def clone_into(self, other):
        self.edit.clone_into(other.edit)

    def _focusIn(self):
        self.btn.show()

    def _focusOut(self, txt):
        self.btn.hide()
        self.focusOut.emit(txt)

    def _focusOutViaKeyPress(self, txt):
        self.btn.hide()
        self.focusOutViaKeyPress.emit(txt)

    def _textChanged(self, txt):
        self.textChanged.emit(txt)
