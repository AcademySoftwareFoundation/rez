from rezgui.qt import QtCore, QtGui
from rez.packages import get_completions
from rez.vendor.version.requirement import Requirement


class PackageLineEdit(QtGui.QLineEdit):

    packageChangeDone = QtCore.Signal(str)

    def __init__(self, parent=None, paths=None, family_only=False):
        super(PackageLineEdit, self).__init__(parent)
        self.paths = paths
        self.family_only = family_only
        self.default_style = None

        self.completer = QtGui.QCompleter(self)
        self.completer.setCompletionMode(QtGui.QCompleter.PopupCompletion)
        self.completions = QtGui.QStringListModel(self.completer)
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
            self.packageChangeDone.emit(self.text())
            return True
        return super(PackageLineEdit, self).event(event)

    def _textEdited(self, txt):
        words = get_completions(txt,
                                paths=self.paths,
                                family_only=self.family_only)
        self.completions.setStringList(words)

    def _textChanged(self, txt):
        tooltip = ""
        if txt:
            try:
                _ = Requirement(str(txt))
                self._set_style()
            except Exception as e:
                tooltip = str(e)
                self._set_style("QLineEdit { border : 2px solid red;}")
        self.setToolTip(tooltip)

    def _set_style(self, style=None):
        if style is None:
            if self.default_style is not None:
                self.setStyleSheet(self.default_style)
        else:
            if self.default_style is None:
                self.default_style = self.styleSheet()
            self.setStyleSheet(style)
