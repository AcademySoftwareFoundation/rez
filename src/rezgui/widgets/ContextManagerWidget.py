from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane
from rezgui.widgets.VariantSummaryWidget import VariantSummaryWidget
from rezgui.widgets.VariantDetailsWidget import VariantDetailsWidget
from rezgui.widgets.ConfiguredSplitter import ConfiguredSplitter
from rezgui.widgets.PackageVersionsList import PackageVersionsList
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.widgets.ContextTableWidget import ContextTableWidget
from rezgui.widgets.SettingsWidget import SettingsWidget
from rezgui.dialogs.ResolveDialog import ResolveDialog
from rez.vendor.version.requirement import Requirement
from rez.vendor.schema.schema import Schema
from rezgui.config import config as rezgui_config
from rez.config import config
from functools import partial


class ContextManagerWidget(QtGui.QWidget):

    settings_schema = Schema({
        "packages_path":        [basestring],
        "implicit_packages":    [basestring]
    })

    def __init__(self, parent=None):
        super(ContextManagerWidget, self).__init__(parent)
        self.load_context = None
        self.current_context = None

        # context settings
        settings = {
            "packages_path":        config.packages_path,
            "implicit_packages":    config.implicit_packages
        }
        self.settings = SettingsWidget(data=settings,
                                       schema=self.settings_schema)

        # widgets
        self.context_table = ContextTableWidget(self.settings)

        menu = QtGui.QMenu()
        a1 = QtGui.QAction("Resolve", self)
        a1.triggered.connect(self._resolve)
        menu.addAction(a1)
        a2 = QtGui.QAction("Advanced...", self)
        a2.triggered.connect(partial(self._resolve, advanced=True))
        menu.addAction(a2)

        resolve_btn = QtGui.QToolButton()
        szpol = QtGui.QSizePolicy()
        szpol.setHorizontalPolicy(QtGui.QSizePolicy.Ignored)
        resolve_btn.setSizePolicy(szpol)
        resolve_btn.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
        resolve_btn.setDefaultAction(a1)
        resolve_btn.setMenu(menu)

        self.diff_btn = QtGui.QPushButton("Diff Mode")
        btn_pane = create_pane([None, self.diff_btn, resolve_btn], False)

        self.variant_summary = VariantSummaryWidget()
        self.package_versions_list = PackageVersionsList()
        self.variant_details = VariantDetailsWidget()

        self.package_tab = QtGui.QTabWidget()
        self.package_tab.addTab(self.variant_summary, "package summary")
        self.package_tab.addTab(self.package_versions_list, "versions")
        self.package_tab.addTab(self.variant_details, "details")

        bottom_pane = create_pane([(self.package_tab, 1), btn_pane], True)

        context_splitter = ConfiguredSplitter(rezgui_config, "layout/splitter/main")
        context_splitter.setOrientation(QtCore.Qt.Vertical)
        context_splitter.addWidget(self.context_table)
        context_splitter.addWidget(bottom_pane)
        if not context_splitter.apply_saved_layout():
            context_splitter.setStretchFactor(0, 2)
            context_splitter.setStretchFactor(1, 1)

        self.resolve_details_edit = StreamableTextEdit()
        self.resolve_details_edit.setStyleSheet("font: 9pt 'Courier'")

        self.tab = QtGui.QTabWidget()
        self.tab.addTab(context_splitter, "context")
        self.tab.addTab(self.settings, "context settings")
        self.tab.addTab(self.resolve_details_edit, "resolve details")

        # layout
        layout = QtGui.QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tab)
        self.setLayout(layout)

        # signals
        self.settings.changes_applied.connect(self.context_table.refresh)
        self.context_table.contextModified.connect(self._contextModified)
        self.context_table.variantSelected.connect(self._variantSelected)
        self.package_tab.currentChanged.connect(self._packageTabChanged)

    def _resolve(self, advanced=False):
        # get and validate request from context table
        request = []
        for req_str in self.context_table.get_request():
            try:
                req = Requirement(req_str)
                request.append(req)
            except Exception as e:
                title = "Invalid package request - %r" % req_str
                QtGui.QMessageBox.warning(self, title, str(e))
                return None

        # do the resolve, set as current if successful
        dlg = ResolveDialog(self.settings, parent=self, advanced=advanced)
        if dlg.resolve(request):
            self.current_context = dlg.get_context()
            self.context_table.set_context(self.current_context)
            self.diff_btn.setEnabled(True)

            self.resolve_details_edit.clear()
            self.current_context.print_info(buf=self.resolve_details_edit)

    def _contextModified(self):
        self.diff_btn.setEnabled(False)

    def _variantSelected(self, variant):
        self._set_variant(variant)

    def _packageTabChanged(self, index):
        variant = self.context_table.current_variant()
        self._set_variant(variant)

    def _set_variant(self, variant):
        widget = self.package_tab.currentWidget()
        if widget:
            widget.set_variant(variant)
        self.package_tab.setEnabled(variant is not None)
