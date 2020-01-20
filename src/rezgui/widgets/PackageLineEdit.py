from Qt import QtCore, QtWidgets, QtGui
from rezgui.models.ContextModel import ContextModel
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rez.packages import get_completions, iter_packages
from rez.vendor.version.requirement import Requirement


class PackageLineEdit(QtWidgets.QLineEdit, ContextViewMixin):

    focusOutViaKeyPress = QtCore.Signal(str)
    focusOut = QtCore.Signal(str)
    focusIn = QtCore.Signal()

    def __init__(self, context_model=None, parent=None, family_only=False,
                 read_only=False):
        super(PackageLineEdit, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)
        self.read_only = read_only
        self.family_only = family_only
        self.default_style = None

        pal = self.palette()
        self.normal_font = self.font()
        self.placeholder_font = self.font()
        self.placeholder_font.setItalic(True)
        self.normal_text_color = pal.color(QtGui.QPalette.Text)
        self.placeholder_text_color = pal.color(QtGui.QPalette.Disabled,
                                                QtGui.QPalette.Text)
        if not self.read_only:
            self.setPlaceholderText("enter package")
            self._update_font()

        self.completer = QtWidgets.QCompleter(self)
        self.completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.completions = QtCore.QStringListModel(self.completer)
        self.completer.setModel(self.completions)
        self.setCompleter(self.completer)

        self.textEdited.connect(self._textEdited)
        self.textChanged.connect(self._textChanged)

    def mouseReleaseEvent(self, event):
        if not self.hasSelectedText():
            self.completer.complete()

    def event(self, event):
        # keyPressEvent does not capture tab
        if event.type() == QtCore.QEvent.KeyPress \
                and event.key() in (QtCore.Qt.Key_Tab,
                                    QtCore.Qt.Key_Enter,
                                    QtCore.Qt.Key_Return):
            self._update_status()
            self.focusOutViaKeyPress.emit(self.text())
            return True
        return super(PackageLineEdit, self).event(event)

    def focusInEvent(self, event):
        self._update_font()
        self.focusIn.emit()
        return super(PackageLineEdit, self).focusInEvent(event)

    def focusOutEvent(self, event):
        self._update_status()
        self._update_font()
        self.focusOut.emit(self.text())
        return super(PackageLineEdit, self).focusOutEvent(event)

    def clone_into(self, other):
        other.family_only = self.family_only
        other.default_style = self.default_style
        other.setText(self.text())
        other.setStyleSheet(self.styleSheet())
        completions = self.completions.stringList()
        other.completions.setStringList(completions)
        other.completer.setCompletionPrefix(self.text())

    def _textChanged(self, txt):
        self._update_font()

    def _update_font(self):
        if self.read_only:
            return
        elif self.text():
            font = self.normal_font
            color = self.normal_text_color
        else:
            font = self.placeholder_font
            color = self.placeholder_text_color

        self.setFont(font)
        pal = self.palette()
        pal.setColor(QtGui.QPalette.Active, QtGui.QPalette.Text, color)
        pal.setColor(QtGui.QPalette.Inactive, QtGui.QPalette.Text, color)
        self.setPalette(pal)

    def _contextChanged(self, flags=0):
        if flags & ContextModel.PACKAGES_PATH_CHANGED:
            self._update_status()

    @property
    def _paths(self):
        return self.context_model.packages_path

    def _textEdited(self, txt):
        words = get_completions(str(txt),
                                paths=self._paths,
                                family_only=self.family_only)
        self.completions.setStringList(list(reversed(list(words))))

    def _set_style(self, style=None):
        if style is None:
            if self.default_style is not None:
                self.setStyleSheet(self.default_style)
        else:
            if self.default_style is None:
                self.default_style = self.styleSheet()
            self.setStyleSheet(style)

    def _update_status(self):
        def _ok():
            self._set_style()
            self.setToolTip("")

        def _err(msg, color="red"):
            self._set_style("QLineEdit { border : 2px solid %s;}" % color)
            self.setToolTip(msg)

        txt = str(self.text())
        if not txt:
            _ok()
            return

        try:
            req = Requirement(str(txt))
        except Exception as e:
            _err(str(e))
            return

        _ok()
        if not req.conflict:
            try:
                it = iter_packages(name=req.name,
                                   range_=req.range,
                                   paths=self._paths)
                pkg = sorted(it, key=lambda x: x.version)[-1]
            except Exception:
                _err("cannot find package: %r" % txt, "orange")
                return

            if pkg.description:
                self.setToolTip(pkg.description)


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
