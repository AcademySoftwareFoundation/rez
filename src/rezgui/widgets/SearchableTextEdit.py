from rezgui.qt import QtCore, QtGui
from rezgui.widgets.FindPopup import FindPopup


class SearchableTextEdit(QtGui.QTextEdit):
    """A TextEdit that can be searched.
    """
    def __init__(self, parent=None):
        super(SearchableTextEdit, self).__init__(parent)
        self.searchable = True
        self.popup = None

    def set_searchable(self, enable):
        self.searchable = enable

    def search(self):
        if not self.searchable:
            return

        self.popup = FindPopup(self, "bottomLeft", close_on_find=False, parent=self)
        self.popup.find.connect(self._find_text)
        self.popup.show()

    def _find_text(self, word):
        if not self.find(word):
            # search from top
            self.moveCursor(QtGui.QTextCursor.Start)
            self.find(word)
