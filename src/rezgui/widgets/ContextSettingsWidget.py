# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from Qt import QtWidgets
from rezgui.util import create_pane
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
from rez.config import config
from rez.vendor import yaml
from rez.vendor.six import six
from rez.vendor.yaml.error import YAMLError
from rez.vendor.schema.schema import Schema, SchemaError, Or, And, Use
from functools import partial


basestring = six.string_types[0]


class ContextSettingsWidget(QtWidgets.QWidget, ContextViewMixin):

    titles = {
        "packages_path":        "Search path for Rez packages",
        "implicit_packages":    "Packages that are implicitly added to the request",
        "package_filter":       "Package exclusion/inclusion rules",
        "caching":              "Enables resolve caching"
    }

    schema_dict = {
        "packages_path":        [basestring],
        "implicit_packages":    [basestring],
        "package_filter":       Or(And(None, Use(lambda x: [])),
                                   And(dict, Use(lambda x: [x])),
                                   [dict]),
        "caching":              bool
    }

    def __init__(self, context_model=None, attributes=None, parent=None):
        """
        Args:
            attributes (list of str): Select only certain settings to expose. If
                None, all settings are exposed.
        """
        super(ContextSettingsWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

        self.schema_keys = set(self.schema_dict.keys())
        if attributes:
            self.schema_keys &= set(attributes)
            assert self.schema_keys

        schema_dict = dict((k, v) for k, v in self.schema_dict.items()
                           if k in self.schema_keys)
        self.schema = Schema(schema_dict)

        self.edit = QtWidgets.QTextEdit()
        self.edit.setStyleSheet("font: 12pt 'Courier'")
        self.default_btn = QtWidgets.QPushButton("Set To Defaults")
        self.discard_btn = QtWidgets.QPushButton("Discard Changes...")
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.discard_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)
        btn_pane = create_pane([None, self.default_btn, self.discard_btn,
                                self.apply_btn], True)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.edit)
        layout.addWidget(btn_pane)
        self.setLayout(layout)

        self.apply_btn.clicked.connect(self.apply_changes)
        self.default_btn.clicked.connect(self.set_defaults)
        self.discard_btn.clicked.connect(partial(self.discard_changes, True))
        self.edit.textChanged.connect(self._settingsChanged)

        self._update_text()

    def _contextChanged(self, flags=0):
        if not (flags & ContextModel.CONTEXT_CHANGED):
            return
        self._update_text()

    def apply_changes(self):
        def _content_error(title, text):
            ret = QtWidgets.QMessageBox.warning(self, title, text,
                                            QtWidgets.QMessageBox.Discard,
                                            QtWidgets.QMessageBox.Cancel)
            if ret == QtWidgets.QMessageBox.Discard:
                self.discard_changes()

        # load new content
        try:
            txt = self.edit.toPlainText()
            data = yaml.load(str(txt), Loader=yaml.FullLoader)
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

        # apply to context model
        self.context_model.set_packages_path(data["packages_path"])
        self.context_model.set_package_filter(data["package_filter"])
        self.context_model.set_caching(data["caching"])
        self._update_text()

    def discard_changes(self, prompt=False):
        if prompt:
            ret = QtWidgets.QMessageBox.warning(
                self,
                "The context settings have been modified.",
                "Your changes will be lost. Are you sure?",
                QtWidgets.QMessageBox.Ok,
                QtWidgets.QMessageBox.Cancel)
            if ret != QtWidgets.QMessageBox.Ok:
                return

        self._update_text()

    def set_defaults(self):
        packages_path = config.packages_path
        caching = config.caching
        implicits = [str(x) for x in config.implicit_packages]
        package_filter = config.package_filter

        data = {"packages_path": packages_path,
                "implicit_packages": implicits,
                "package_filter": package_filter,
                "caching": caching}
        data = dict((k, v) for k, v in data.items()
                    if k in self.schema_keys)

        self._set_text(data)
        self.discard_btn.setEnabled(True)
        self.apply_btn.setEnabled(True)

    def _update_text(self):
        model = self.context_model
        implicits = [str(x) for x in model.implicit_packages]
        data = {"packages_path": model.packages_path,
                "implicit_packages": implicits,
                "package_filter": model.package_filter,
                "caching": model.caching}
        data = dict((k, v) for k, v in data.items()
                    if k in self.schema_keys)

        self._set_text(data)
        self.discard_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)

    def _set_text(self, data):
        lines = []
        for key, value in data.items():
            lines.append('')
            txt = yaml.dump({key: value}, default_flow_style=False)
            title = self.titles.get(key)
            if title:
                lines.append("# %s" % title)
            lines.append(txt.rstrip())

        txt = '\n'.join(lines) + '\n'
        txt = txt.lstrip()
        self.edit.setPlainText(txt)

    def _settingsChanged(self):
        self.discard_btn.setEnabled(True)
        self.apply_btn.setEnabled(True)
