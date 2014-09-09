from rezgui.qt import QtCore, QtGui
from rezgui.widgets.EffectivePackageCellWidget import EffectivePackageCellWidget
from rezgui.widgets.PackageSelectWidget import PackageSelectWidget
from rezgui.widgets.VariantCellWidget import VariantCellWidget
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
from rez.packages import Variant
from functools import partial


class ContextTableWidget(QtGui.QTableWidget, ContextViewMixin):
    default_row_count = 10

    #contextModified = QtCore.Signal()
    variantSelected = QtCore.Signal(object)

    def __init__(self, context_model=None, parent=None):
        """Create a context table.

        Args:
            settings (`SettingsWidget`): Context settings, such as search path.
                Ignored if `read_only` is True.
        """
        super(ContextTableWidget, self).__init__(self.default_row_count,
                                                 2, parent)
        ContextViewMixin.__init__(self, context_model)

        self.diff_mode = False
        self._show_effective_request = False
        self._current_variant = None

        self.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)

        hh = self.horizontalHeader()
        hh.setDefaultSectionSize(12 * self.fontMetrics().height())

        vh = self.verticalHeader()
        vh.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        vh.setVisible(False)

        self.currentCellChanged.connect(self._currentCellChanged)
        self.itemSelectionChanged.connect(self._itemSelectionChanged)
        self.refresh()

    def selectionCommand(self, index, event=None):
        row = index.row()
        column = index.column()

        widget = self.cellWidget(row, column)
        if widget and isinstance(widget, VariantCellWidget):
            return QtGui.QItemSelectionModel.ClearAndSelect
        else:
            return QtGui.QItemSelectionModel.Clear

    def current_variant(self):
        """Returns the currently selected variant, if any."""
        return self._current_variant

    def show_effective_request(self, b):
        if b != self._show_effective_request:
            self._show_effective_request = b
            self._update_column(0)

    def get_request(self):
        """Get the current request list.

        Returns:
            List of strings.
        """
        return self._get_request(0)

    def refresh(self):
        self._contextChanged(ContextModel.CONTEXT_CHANGED)

    def _contextChanged(self, flags=0):
        update_request = False
        if flags & ContextModel.CONTEXT_CHANGED:
            self.clear()
            self.setHorizontalHeaderLabels(["request", "resolve"])

            if self.context():
                self._apply_context(self.context_model, 0, 1)
            else:
                self._set_package_cell(0, 0)
            update_request = True

        if flags & ContextModel.LOCKS_CHANGED and self._show_effective_request:
            update_request = True

        if update_request:
            self._update_column(0)

    def _update_column(self, column):
        # remove effective request cells
        for row, widget in self._iter_column_widgets(column, EffectivePackageCellWidget):
            self.removeCellWidget(row, column)

        # update effective request cells
        if self._show_effective_request:
            # get row following package select widgets
            last_row = -1
            for row, widget in self._iter_column_widgets(column, PackageSelectWidget):
                last_row = row

            row = last_row + 1
            for request_str in self.context_model.implicit_packages:
                self._set_effective_package_cell(row, column, request_str, "implicit")
                row += 1

            d = self.context_model.get_lock_requests()
            for lock, requests in d.iteritems():
                for request in requests:
                    request_str = str(request)
                    self._set_effective_package_cell(row, column, request_str, lock.name)
                    row += 1

        self._trim_trailing_rows()

    def _currentCellChanged(self, currentRow, currentColumn,
                            previousRow, previousColumn):
        widget = self.cellWidget(currentRow, currentColumn)
        if widget and isinstance(widget, VariantCellWidget):
            self._current_variant = widget.variant
        else:
            self._current_variant = None
            self.setCurrentIndex(QtCore.QModelIndex())
        self.variantSelected.emit(self._current_variant)

    # this is only here to clear the current index, which leaves an annoying
    # visual cue even though the cell is not selected
    def _itemSelectionChanged(self):
        if not self.selectedIndexes():
            self.setCurrentIndex(QtCore.QModelIndex())

    def _iter_column_widgets(self, column, types=None):
        types = types or QtGui.QWidget
        for row in range(self.rowCount()):
            widget = self.cellWidget(row, column)
            if widget and isinstance(widget, types):
                yield row, widget

    def _get_request(self, column):
        request_strs = []
        for _, edit in self._iter_column_widgets(column, PackageSelectWidget):
            txt = str(edit.text()).strip()
            if txt:
                request_strs.append(txt)
        return request_strs

    def _apply_context(self, context_model, request_column, resolve_column):
        context = context_model.context()
        requests = context.requested_packages()
        resolved = context.resolved_packages[:]
        num_requests = len(requests)
        consumed = set()

        for i, request in enumerate(requests):
            self._set_package_cell(i, request_column, request)
            variant = context.get_resolved_package(request.name)
            if variant and variant.name not in consumed:
                consumed.add(variant.name)
                self._set_variant_cell(i, resolve_column, context_model, variant)
                resolved = [x for x in resolved if x.name != request.name]

        for i, variant in enumerate(resolved):
            self._set_variant_cell(i + num_requests, resolve_column,
                                   context_model, variant)

        self._set_package_cell(num_requests, request_column)

    def _set_package_cell(self, row, column, request=None):
        if row >= self.rowCount():
            self.setRowCount(row + 1)

        if request is None:
            # don't overwrite existing package request
            widget = self.cellWidget(row, column)
            if widget and isinstance(widget, PackageSelectWidget):
                return None

        txt = str(request) if request else ""

        edit = PackageSelectWidget(self.context_model)
        edit.setText(txt)
        self.setCellWidget(row, column, edit)
        edit.textChanged.connect(partial(self._packageTextChanged, row, column))
        edit.focusOut.connect(partial(self._packageFocusOut, row, column))
        edit.focusOutViaKeyPress.connect(partial(self._packageFocusOutViaKeyPress,
                                                 row, column))
        return edit

    def _set_effective_package_cell(self, row, column, request, lock_type):
        if row >= self.rowCount():
            self.setRowCount(row + 1)
        cell = EffectivePackageCellWidget(request, lock_type)
        self.setCellWidget(row, column, cell)

    def _set_variant_cell(self, row, column, context_model, variant):
        if row >= self.rowCount():
            self.setRowCount(row + 1)
        widget = VariantCellWidget(context_model, variant)
        self.setCellWidget(row, column, widget)

    def _set_cell_text(self, row, column, txt):
        if row >= self.rowCount():
            self.setRowCount(row + 1)

        if self.cellWidget(row, column):
            self.removeCellWidget(row, column)
        item = QtGui.QTableWidgetItem(txt)
        self.setItem(row, column, item)

    def _packageTextChanged(self, row, column, txt):
        if txt:
            if self._set_package_cell(row + 1, column):
                self._update_column(column)

    def _packageFocusOutViaKeyPress(self, row, column, txt):
        if txt:
            self._set_current_cell(row + 1, column)
        else:
            widget = self.cellWidget(row + 1, column)
            if widget and isinstance(widget, PackageSelectWidget):
                self._delete_cell(row, column)

            new_request = self.get_request()
            self.context_model.set_request(new_request)
            self._update_column(column)

    def _packageFocusOut(self, row, column, txt):
        if txt:
            self._set_package_cell(row + 1, column)
        else:
            widget = self.cellWidget(row + 1, column)
            if widget and isinstance(widget, PackageSelectWidget):
                self._delete_cell(row, column)

        new_request = self.get_request()
        self.context_model.set_request(new_request)
        self._update_column(column)

    def _delete_cell(self, row, column):
        for i in range(row, self.rowCount()):
            edit = self.cellWidget(i, column)
            if edit and isinstance(edit, PackageSelectWidget):
                next_edit = self.cellWidget(i + 1, column)
                if next_edit and isinstance(next_edit, PackageSelectWidget):
                    next_edit.clone_into(edit)
                else:
                    self.removeCellWidget(i, column)

    def _trim_trailing_rows(self):
        n = 0
        for i in reversed(range(self.default_row_count, self.rowCount())):
            row_clear = not any(self.cellWidget(i, x)
                                for x in range(self.columnCount()))
            if row_clear:
                n += 1
            else:
                break
        if n:
            row, column = self.currentRow(), self.currentColumn()
            self.setRowCount(self.rowCount() - n)
            self._set_current_cell(row, column)

    def _set_current_cell(self, row, column):
        self.setCurrentCell(row, column)
        edit = self.cellWidget(row, column)
        if edit:
            edit.setFocus()
