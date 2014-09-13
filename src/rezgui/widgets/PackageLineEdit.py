from rezgui.qt import QtCore, QtGui
from rezgui.models.ContextModel import ContextModel
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rez.exceptions import RezError
from rez.packages import get_completions, iter_packages
from rez.vendor.version.requirement import Requirement


class PackageLineEdit(QtGui.QLineEdit, ContextViewMixin):

    focusOutViaKeyPress = QtCore.Signal(str)
    focusOut = QtCore.Signal(str)
    focusIn = QtCore.Signal()

    def __init__(self, context_model=None, parent=None, family_only=False):
        super(PackageLineEdit, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)
        self.family_only = family_only
        self.default_style = None

        pal = self.palette()
        self.normal_font = self.font()
        self.normal_disabled_text_color = pal.color(QtGui.QPalette.Disabled,
                                                    QtGui.QPalette.Text)
        self.placeholder_font = self.font()
        self.placeholder_font.setItalic(True)
        self.setFont(self.placeholder_font)
        self.setPlaceholderText("enter package")

        # testing
        #pal.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text,
        #             pal.color(QtGui.QPalette.Text))

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
            self._update_status()
            self.focusOutViaKeyPress.emit(self.text())
            return True
        return super(PackageLineEdit, self).event(event)

    def focusInEvent(self, event):
        self.focusIn.emit()
        return super(PackageLineEdit, self).focusInEvent(event)

    def focusOutEvent(self, event):
        self._update_status()
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
        font = self.normal_font if txt else self.placeholder_font
        self.setFont(font)

    def _contextChanged(self, flags=0):
        if flags & ContextModel.PACKAGES_PATH_CHANGED:
            self._update_status()

    @property
    def _paths(self):
        return self.context_model.packages_path

    def _textEdited(self, txt):
        words = get_completions(txt,
                                paths=self._paths,
                                family_only=self.family_only)
        self.completions.setStringList(list(reversed(words)))

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
                                   range=req.range,
                                   paths=self._paths)
                pkg = sorted(it, key=lambda x: x.version)[-1]
            except Exception:
                _err("cannot find package: %r" % txt, "orange")
                return

            if pkg.description:
                self.setToolTip(pkg.description)
