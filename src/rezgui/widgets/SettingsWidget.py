from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane
from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError
from rez.vendor.schema.schema import SchemaError


class SettingsWidget(QtGui.QWidget):

    changes_applied = QtCore.Signal()

    def __init__(self, parent=None, schema=None, data=None):
        super(SettingsWidget, self).__init__(parent)
        self.schema = schema
        self.data = data or {}

        self.edit = QtGui.QTextEdit()
        apply_btn = QtGui.QPushButton("Apply")
        btn_pane = create_pane([None, apply_btn], True)

        layout = QtGui.QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit)
        layout.addWidget(btn_pane)
        self.setLayout(layout)

        apply_btn.clicked.connect(self._apply)

        self._update_text()

    def get(self, key):
        return self.data.get(key)

    def _apply(self):
        def _content_error(title, text):
            ret = QtGui.QMessageBox.warning(self, title, text,
                                            QtGui.QMessageBox.Reset,
                                            QtGui.QMessageBox.Cancel)
            if ret == QtGui.QMessageBox.Reset:
                self._update_text()

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
        self.changes_applied.emit()

    def _update_text(self):
        txt = yaml.dump(self.data, default_flow_style=False)
        self.edit.setPlainText(txt)
