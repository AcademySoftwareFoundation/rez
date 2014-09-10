from rezgui.qt import QtCore, QtGui
from rezgui.util import update_font
from rezgui.widgets.EffectivePackageCellWidget import EffectivePackageCellWidget
from rezgui.widgets.PackageSelectWidget import PackageSelectWidget
from rezgui.widgets.VariantCellWidget import VariantCellWidget
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
from rez.packages import Variant
from rez.vendor.version.requirement import Requirement
from functools import partial


class CellDelegate(QtGui.QStyledItemDelegate):
    def __init__(self, context_model=None, parent=None):
        super(CellDelegate, self).__init__(parent)
        pal = QtGui.QPalette()
        col = pal.color(QtGui.QPalette.Active, QtGui.QPalette.Window)
        self.pen = QtGui.QPen(col)
        self.stale_pen = QtGui.QPen(QtGui.QColor("red"))
        self.stale_pen.setWidth(2)

    def paint(self, painter, option, index):
        super(CellDelegate, self).paint(painter, option, index)
        row = index.row()
        column = index.column()
        table = self.parent()
        stale = table.context_model.is_stale()
        rect = option.rect
        oldpen = painter.pen()

        def _setpen(to_stale):
            pen = self.stale_pen if stale and to_stale else self.pen
            painter.setPen(pen)

        r = (rect.topRight(), rect.bottomRight())
        b = (rect.bottomLeft(), rect.bottomRight() - QtCore.QPoint(1, 0))
        _setpen(column < 2)

        if column == 0:
            painter.drawLine(*r)
            _setpen(False)
            painter.drawLine(*b)
        elif column == 1:
            painter.drawLine(*r)
            if row == table.rowCount() - 1:
                painter.drawLine(*b)
            else:
                if row == 0:
                    painter.drawLine(rect.topLeft(), rect.topRight())
                _setpen(False)
                painter.drawLine(*b)
        elif column == 2:
            painter.drawLine(*r)
        else:
            painter.drawLine(*r)
            painter.drawLine(*b)

        painter.setPen(oldpen)


class ContextTableWidget(QtGui.QTableWidget, ContextViewMixin):
    default_row_count = 10

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
        self.diff_context_model = None
        self._show_effective_request = False
        self._current_variant = None

        self.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)

        hh = self.horizontalHeader()
        hh.setDefaultSectionSize(12 * self.fontMetrics().height())

        vh = self.verticalHeader()
        vh.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        vh.setVisible(False)

        self.delegate = CellDelegate(self.context_model, self)
        self.setItemDelegate(self.delegate)
        self.setShowGrid(False)

        self.currentCellChanged.connect(self._currentCellChanged)
        self.itemSelectionChanged.connect(self._itemSelectionChanged)
        self.refresh()

    def selectionCommand(self, index, event=None):
        row = index.row()
        column = index.column()

        widget = self.cellWidget(row, column)
        if widget and widget.isEnabled() and isinstance(widget, VariantCellWidget):
            return QtGui.QItemSelectionModel.ClearAndSelect
        else:
            return QtGui.QItemSelectionModel.Clear

    def current_variant(self):
        """Returns the currently selected variant, if any."""
        return self._current_variant

    def show_effective_request(self, b):
        if b != self._show_effective_request:
            self._show_effective_request = b
            self._update_column(0, self.context_model)
            if self.diff_mode:
                self._update_column(4, self.diff_context_model)

    def get_request(self):
        """Get the current request list.

        Returns:
            List of strings.
        """
        return self._get_request(0)

    def set_diff_mode(self, b):
        """Enable/disable diff mode."""
        if b == self.diff_mode:
            return

        assert self.context_model.context()
        self.diff_mode = b

        if self.diff_mode:
            assert not self.context_model.is_stale()
            self.clear()
            self.setColumnCount(5)
            self.diff_context_model = self.context_model.copy()
        else:
            self.diff_context_model = None
            self.setColumnCount(2)

        self.refresh()

    def revert_to_diff(self):
        assert self.diff_mode
        source_context = self.diff_context_model.context()
        self.context_model.set_context(source_context)

    def refresh(self):
        self._contextChanged(ContextModel.CONTEXT_CHANGED)

    def _contextChanged(self, flags=0):
        update_request_columns = {}
        if flags & ContextModel.CONTEXT_CHANGED:
            self.clear()
            self.setHorizontalHeaderLabels(["request", "resolve"])

            if self.context():
                if self.diff_mode:
                    item = QtGui.QTableWidgetItem("")
                    self.setHorizontalHeaderItem(2, item)
                    hh = self.horizontalHeader()
                    hh.setResizeMode(2, QtGui.QHeaderView.Fixed)
                    self.setColumnWidth(2, 20)

                    for label, column in (("resolve", 3), ("request", 4)):
                        item = QtGui.QTableWidgetItem(label)
                        update_font(item, italic=True)
                        self.setHorizontalHeaderItem(column, item)

                    self._apply_request(self.diff_context_model, 4)
                    self._apply_resolve(self.diff_context_model, 3, 4)
                    self._apply_request(self.context_model, 0)
                    self._apply_resolve(self.context_model, 1, 3)
                    update_request_columns[3] = self.diff_context_model
                else:
                    self._apply_request(self.context_model, 0)
                    self._apply_resolve(self.context_model, 1, 0)
            else:
                self._set_package_cell(0, 0)
            update_request_columns[0] = self.context_model

        if flags & ContextModel.LOCKS_CHANGED and self._show_effective_request:
            update_request_columns[0] = self.context_model

        for column, context_model in update_request_columns.iteritems():
            self._update_column(column, context_model)

        if self.context_model.is_stale():
            item1 = QtGui.QTableWidgetItem("request*")
            item2 = QtGui.QTableWidgetItem("resolve (stale)")
            update_font(item2, italic=True)
        else:
            item1 = QtGui.QTableWidgetItem("request")
            item2 = QtGui.QTableWidgetItem("resolve")
        self.setHorizontalHeaderItem(0, item1)
        self.setHorizontalHeaderItem(1, item2)
        self.update()

    def _update_column(self, column, context_model):
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
            for request_str in context_model.implicit_packages:
                self._set_effective_package_cell(row, column, request_str, "implicit")
                row += 1

            d = context_model.get_lock_requests()
            for lock, requests in d.iteritems():
                for request in requests:
                    request_str = str(request)
                    self._set_effective_package_cell(row, column, request_str, lock.name)
                    row += 1

        self._trim_trailing_rows()

    def _currentCellChanged(self, currentRow, currentColumn,
                            previousRow, previousColumn):
        widget = self.cellWidget(currentRow, currentColumn)
        if widget and widget.isEnabled() and isinstance(widget, VariantCellWidget):
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

    def _apply_request(self, context_model, column):
        context = context_model.context()
        requests = context.requested_packages()
        num_requests = len(requests)
        for i, request in enumerate(requests):
            self._set_package_cell(i, column, request)
        self._set_package_cell(num_requests, column)

    def _apply_resolve(self, context_model, column, source_column):
        context = context_model.context()
        resolved = context.resolved_packages[:]
        consumed_rows = set()

        # match variants up with matching request/variant in source column
        for row, widget in self._iter_column_widgets(
                source_column, (PackageSelectWidget, VariantCellWidget)):
            request_str = str(widget.text())
            if not request_str:
                continue

            package_name = Requirement(request_str).name
            matches = [x for x in resolved if x.name == package_name]
            if matches:
                variant = matches[0]
                resolved = [x for x in resolved if x.name != package_name]
                source_variant = widget.variant \
                    if isinstance(widget, VariantCellWidget) else None
                self._set_variant_cell(row, column, context_model, variant,
                                       source_variant=source_variant)

            consumed_rows.add(row)

        # place variants that don't match requests/variants in source column
        row = 0
        while resolved:
            variant = resolved[0]
            resolved = resolved[1:]
            while row in consumed_rows:
                row += 1
            self._set_variant_cell(row, column, context_model, variant)
            row += 1

    def _set_package_cell(self, row, column, request=None):
        if row >= self.rowCount():
            self.setRowCount(row + 1)

        if request is None:
            # don't overwrite existing package request
            widget = self.cellWidget(row, column)
            if widget and isinstance(widget, PackageSelectWidget):
                return None

        txt = str(request) if request else ""
        read_only = (column != 0)

        edit = PackageSelectWidget(self.context_model, read_only=read_only)
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

    def _set_variant_cell(self, row, column, context_model, variant,
                          source_variant=None):
        if row >= self.rowCount():
            self.setRowCount(row + 1)

        widget = VariantCellWidget(context_model, variant,
                                   diff_variant=source_variant)
        self.setCellWidget(row, column, widget)
        widget._set_stale(column != 1)

        if column == 1 and widget.compare_state:
            if widget.compare_state == "equal_to":
                c = (0.8, 0.8, 0.8)
            elif widget.compare_state == "greater_than":
                c = (0, 1, 0)
            else:
                c = (1, 0, 0)
            self._set_cell_color(row, column, c)
            #self._set_cell_color(row, column + 1, c)
            self._set_cell_color(row, column + 2, c)

    def _set_cell_text(self, row, column, txt):
        if row >= self.rowCount():
            self.setRowCount(row + 1)

        if self.cellWidget(row, column):
            self.removeCellWidget(row, column)
        item = QtGui.QTableWidgetItem(txt)
        self.setItem(row, column, item)

    def _set_cell_color(self, row, column, c):
        item = self.item(row, column)
        if item is None:
            item = QtGui.QTableWidgetItem()
            self.setItem(row, column, item)

        f = 0.8
        pal = QtGui.QPalette()
        col = pal.color(QtGui.QPalette.Active, QtGui.QPalette.Base)

        bg_c = (col.redF(), col.greenF(), col.blueF())
        bg_c = [x * f for x in bg_c]
        c = [x * (1 - f) for x in c]
        c = [x + y for x, y in zip(bg_c, c)]

        # have to use 1-px image to get flat shading
        color = QtGui.QColor.fromRgbF(*c)
        img = QtGui.QPixmap(QtCore.QSize(1, 1))
        img.fill(color)

        item.setBackground(QtGui.QBrush(img))

    def _packageTextChanged(self, row, column, txt):
        if txt:
            if self._set_package_cell(row + 1, column):
                self._update_column(column, self.context_model)

    def _packageFocusOutViaKeyPress(self, row, column, txt):
        if txt:
            self._set_current_cell(row + 1, column)
        else:
            widget = self.cellWidget(row + 1, column)
            if widget and isinstance(widget, PackageSelectWidget):
                self._delete_cell(row, column)

            new_request = self.get_request()
            self.context_model.set_request(new_request)
            self._update_column(column, self.context_model)

    def _packageFocusOut(self, row, column, txt):
        if txt:
            self._set_package_cell(row + 1, column)
        else:
            widget = self.cellWidget(row + 1, column)
            if widget and isinstance(widget, PackageSelectWidget):
                self._delete_cell(row, column)

        new_request = self.get_request()
        self.context_model.set_request(new_request)
        self._update_column(column, self.context_model)

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
