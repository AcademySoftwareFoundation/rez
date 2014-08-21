from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane
from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError
from rez.vendor.schema.schema import SchemaError


class SettingsWidget(QtGui.QWidget):

    settingsApplied = QtCore.Signal()
    settingsChanged = QtCore.Signal()
    settingsChangesDiscarded = QtCore.Signal()

    def __init__(self, parent=None, schema=None, data=None):
        super(SettingsWidget, self).__init__(parent)
        self.schema = schema
        self.data = data or {}

        self.edit = QtGui.QTextEdit()
        self.edit.setStyleSheet("font: 9pt 'Courier'")
        self.discard_btn = QtGui.QPushButton("Discard Changes...")
        self.apply_btn = QtGui.QPushButton("Apply")
        self.discard_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)
        btn_pane = create_pane([None, self.discard_btn, self.apply_btn], True)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.edit)
        layout.addWidget(btn_pane)
        self.setLayout(layout)

        self.apply_btn.clicked.connect(self.apply_changes)
        self.discard_btn.clicked.connect(self.discard_changes)
        self.edit.textChanged.connect(self._settingsChanged)

        self._update_text()

    def reset(self, data):
        self.data = data or {}
        self._update_text()

    def get(self, key):
        return self.data.get(key)

    def pending_changes(self):
        return self.apply_btn.isEnabled()

    def apply_changes(self):
        def _content_error(title, text):
            ret = QtGui.QMessageBox.warning(self, title, text,
                                            QtGui.QMessageBox.Discard,
                                            QtGui.QMessageBox.Cancel)
            if ret == QtGui.QMessageBox.Discard:
                self._discard_changes()

        # load new content
        try:
            txt = self.edit.toPlainText()
            data = yaml.load(str(txt))
        except YAMLError as e:
            _content_error("Invalid syntax", str(e))
            return

        # check against schema
        if self.schema:
            try:
                data = self.schema.validate(data)
            except SchemaError as e:
                _content_error("Settings validation failure", str(e))
                return

        # apply
        self.data = data
        self._update_text()
        self.settingsApplied.emit()

    def discard_changes(self):
        ret = QtGui.QMessageBox.warning(
            self,
            "The context settings have been modified.",
            "Your changes will be lost. Are you sure?",
            QtGui.QMessageBox.Ok,
            QtGui.QMessageBox.Cancel)
        if ret == QtGui.QMessageBox.Ok:
            self._discard_changes()

    def _discard_changes(self):
        self._update_text()
        self.settingsChangesDiscarded.emit()

    def _update_text(self):
        txt = yaml.dump(self.data, default_flow_style=False)
        self.edit.setPlainText(txt)
        self.discard_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)

    def _settingsChanged(self):
        self.discard_btn.setEnabled(True)
        self.apply_btn.setEnabled(True)
        self.settingsChanged.emit()
