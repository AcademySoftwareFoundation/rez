from rezgui.qt import QtCore, QtGui
from functools import partial


class Config(QtCore.QSettings):
    def __init__(self, default_settings, organization=None, application=None,
                 parent=None):
        super(Config, self).__init__(organization, application, parent)
        self.default_settings = default_settings

    def value(self, key):
        default = self._default_value(key)
        val = super(Config, self).value(key, default)
        if hasattr(val, "toPyObject"):
            val = val.toPyObject()
        if type(val) == type(default):
            return val
        else:
            return self._convert_value(val, type(default))

    def attach(self, widget, key):
        if isinstance(widget, QtGui.QComboBox):
            self._attach_combobox(widget, key)
        elif isinstance(widget, QtGui.QCheckBox):
            self._attach_checkbox(widget, key)
        else:
            raise NotImplementedError

    @classmethod
    def _convert_value(cls, value, type_):
        if type_ is bool:
            return (str(value).lower() == "true")
        else:
            return type_(value)

    def _attach_checkbox(self, widget, key):
        if widget.isTristate():
            raise NotImplementedError

        value = self.value(key)
        widget.setCheckState(QtCore.Qt.Checked if value else QtCore.Qt.Unchecked)
        widget.stateChanged.connect(
            partial(self._checkbox_stateChanged, widget, key))

    def _checkbox_stateChanged(self, widget, key):
        value = widget.isChecked()
        self.setValue(key, value)

    def _attach_combobox(self, widget, key):
        value = self.value(key)
        index = widget.findText(value)
        if index == -1:
            widget.setEditText(value)
        else:
            widget.setCurrentIndex(index)

        widget.currentIndexChanged.connect(
            partial(self._combobox_currentIndexChanged, widget, key))
        widget.editTextChanged.connect(
            partial(self._combobox_editTextChanged, widget, key))

    def _combobox_currentIndexChanged(self, widget, key, index):
        value = widget.itemText(index)
        self.setValue(key, value)

    def _combobox_editTextChanged(self, widget, key, txt):
        self.setValue(key, txt)

    def _default_value(self, key):
        keys = key.lstrip('/').split('/')
        value = self.default_settings
        for k in keys:
            try:
                value = value[k]
            except KeyError:
                raise ValueError("No such application setting: %r" % key)
        return value
