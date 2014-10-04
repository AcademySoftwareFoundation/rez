from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane


class FindPopup(QtGui.QFrame):

    find = QtCore.Signal(str)

    def __init__(self, pivot_widget, words, parent=None):
        super(FindPopup, self).__init__(parent)
        self.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Raised)
        self.setWindowFlags(QtCore.Qt.Popup)

        self.edit = QtGui.QLineEdit()
        self.btn = QtGui.QPushButton("Find")

        create_pane([self.edit, self.btn], True, compact=True,
                    compact_spacing=0, parent_widget=self)
        self.edit.setFocus()

        self.completer = QtGui.QCompleter(self)
        self.completer.setCompletionMode(QtGui.QCompleter.PopupCompletion)
        self.completions = QtGui.QStringListModel(words, self.completer)
        self.completer.setModel(self.completions)
        self.edit.setCompleter(self.completer)

        pt = pivot_widget.rect().bottomLeft()
        global_pt = pivot_widget.mapToGlobal(pt)
        self.move(global_pt)

        self.btn.clicked.connect(self._find)
        self.edit.returnPressed.connect(self._find)

    def _find(self):
        word = self.edit.text()
        self.find.emit(word)
        self.close()
