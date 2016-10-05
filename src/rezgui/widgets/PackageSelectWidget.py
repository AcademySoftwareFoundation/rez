from rezgui.qt import QtCore, QtGui
from rezgui.util import update_font, create_pane
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.dialogs.BrowsePackageDialog import BrowsePackageDialog
from rezgui.widgets.PackageLineEdit import PackageLineEdit
from rezgui.widgets.IconButton import IconButton


class PackageSelectWidget(QtGui.QWidget, ContextViewMixin):

    focusOutViaKeyPress = QtCore.Signal(str)
    focusOut = QtCore.Signal(str)
    textChanged = QtCore.Signal(str)

    def __init__(self, context_model=None, read_only=False, parent=None):
        super(PackageSelectWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

        self.edit = PackageLineEdit(self.context_model, read_only=read_only,
                                    parent=self)
        self.edit.setStyleSheet("QLineEdit { border : 0px;}")
        self.btn = IconButton("package", "browse packages")
        self.btn.hide()

        create_pane([(self.edit, 1), self.btn, 2], True, compact=True,
                    compact_spacing=0, parent_widget=self)

        if read_only:
            self.edit.setReadOnly(True)
            update_font(self.edit, italic=True)
        else:
            self.edit.focusIn.connect(self._focusIn)
            self.edit.focusOut.connect(self._focusOut)
            self.edit.focusOutViaKeyPress.connect(self._focusOutViaKeyPress)
            self.edit.textChanged.connect(self._textChanged)
            self.btn.clicked.connect(self._browse_package)

    def text(self):
        return self.edit.text()

    def setText(self, txt):
        self.edit.setText(txt)

    def clone_into(self, other):
        self.edit.clone_into(other.edit)

    def setFocus(self):
        self.edit.setFocus()
        self.btn.show()

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

    def _browse_package(self, button):
        self.btn.show()
        dlg = BrowsePackageDialog(context_model=self.context_model,
                                  package_text=self.text(),
                                  parent=self.parentWidget())
        dlg.exec_()
        if dlg.package:
            txt = dlg.package.qualified_name
            self.setText(txt)
        self.setFocus()


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
