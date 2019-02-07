from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane


class FindPopup(QtGui.QFrame):

    find = QtCore.Signal(str)

    def __init__(self, pivot_widget, pivot_position=None, words=None,
                 initial_word=None, close_on_find=True, parent=None):
        super(FindPopup, self).__init__(parent)
        self.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Raised)
        self.setWindowFlags(QtCore.Qt.Popup)
        self.close_on_find = close_on_find

        self.edit = QtGui.QLineEdit()
        self.btn = QtGui.QPushButton("Find")
        create_pane([self.edit, self.btn], True, compact=True,
                    compact_spacing=0, parent_widget=self)
        self.edit.setFocus()

        if initial_word:
            self.edit.setText(initial_word)
            self.edit.selectAll()

        self.completer = None
        if words:
            self.completer = QtGui.QCompleter(self)
            self.completer.setCompletionMode(QtGui.QCompleter.PopupCompletion)
            self.completions = QtGui.QStringListModel(words, self.completer)
            self.completer.setModel(self.completions)
            self.edit.setCompleter(self.completer)

        pt = getattr(pivot_widget.rect(), pivot_position)()
        global_pt = pivot_widget.mapToGlobal(pt)
        self.move(global_pt)

        self.btn.clicked.connect(self._find)
        self.edit.returnPressed.connect(self._find)

        find_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self)
        find_shortcut.activated.connect(self._find_again)

    def _find(self):
        word = self.edit.text()
        self.find.emit(word)
        if self.close_on_find:
            self.close()

    def _find_again(self):
        self.edit.selectAll()


