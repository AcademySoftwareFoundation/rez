from rezgui.qt import QtCore, QtGui
from rez.exceptions import RezError
from rez.packages import get_completions, iter_packages
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
            self._update_status(True)
            self.packageChangeDone.emit(self.text())
            return True
        return super(PackageLineEdit, self).event(event)

    def clone_into(self, other):
        other.setText(self.text())
        other.setStyleSheet(self.styleSheet())
        other.paths = self.paths
        other.family_only = self.family_only
        other.default_style = self.default_style

    def _textEdited(self, txt):
        words = get_completions(txt,
                                paths=self.paths,
                                family_only=self.family_only)
        self.completions.setStringList(words)

    def _textChanged(self, txt):
        self._update_status()

    def _set_style(self, style=None):
        if style is None:
            if self.default_style is not None:
                self.setStyleSheet(self.default_style)
        else:
            if self.default_style is None:
                self.default_style = self.styleSheet()
            self.setStyleSheet(style)

    def _update_status(self, identify_package=False):
        def _ok():
            self._set_style()
            self.setToolTip("")

        def _err(msg):
            self._set_style("QLineEdit { border : 2px solid red;}")
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

        if identify_package and not req.conflict:
            try:
                it = iter_packages(name=req.name,
                                   range=req.range,
                                   paths=self.paths)
                pkg = sorted(it, key=lambda x: x.version)[-1]
            except Exception:
                _err("cannot find package: %r" % txt)
                return

            if pkg.description:
                self.setToolTip(pkg.description)
        else:
            _ok()
