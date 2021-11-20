# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
