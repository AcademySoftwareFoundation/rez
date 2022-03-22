# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from Qt import QtWidgets, QtGui
from rezgui.widgets.FindPopup import FindPopup


class SearchableTextEdit(QtWidgets.QTextEdit):
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

        txt = str(self.textCursor().selectedText()).strip()
        if len(txt) < 32 and len(txt.split()) == 1:
            initial_word = txt
        else:
            initial_word = None

        self.popup = FindPopup(self, "bottomLeft", initial_word=initial_word,
                               close_on_find=False, parent=self)
        self.popup.find.connect(self._find_text)
        self.popup.show()

    def _find_text(self, word):
        if not self.find(word):
            # search from top
            self.moveCursor(QtGui.QTextCursor.Start)
            self.find(word)
