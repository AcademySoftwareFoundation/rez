from rezgui.qt import QtGui
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
