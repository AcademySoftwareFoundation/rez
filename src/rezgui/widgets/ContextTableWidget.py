from Qt import QtCompat, QtCore, QtWidgets, QtGui
from rezgui.util import update_font, create_pane, interp_color
from rezgui.widgets.EffectivePackageCellWidget import EffectivePackageCellWidget
from rezgui.widgets.PackageSelectWidget import PackageSelectWidget
from rezgui.widgets.VariantCellWidget import VariantCellWidget
from rezgui.widgets.IconButton import IconButton
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
from rezgui.objects.App import app
from rez.packages import iter_packages
from rez.vendor.version.requirement import Requirement
from rez.vendor.version.version import VersionRange
from functools import partial
import os.path


class CompareCell(QtWidgets.QWidget):
    def __init__(self, context_model, variant_left=None, variant_right=None,
                 parent=None):
        super(CompareCell, self).__init__(parent)
        self.context_model = context_model
        self.left_variant = variant_left
        self.right_variant = variant_right
        self.color = None
        self.side = None
        self.mode = None
        self.comparable = False

        package_paths = self.context_model.packages_path

        widget = None
        if self.left_variant and self.right_variant:
            self.side = "both"
            equal_versions = (self.left_variant.version == self.right_variant.version)
            right_variant_visible = (self.right_variant.wrapped.location in package_paths)
            self.comparable = right_variant_visible and not equal_versions

            if self.comparable:
                # determine how far apart the variant versions are
                versions = sorted([self.left_variant.version,
                                   self.right_variant.version])
                range_ = VersionRange.as_span(*versions)
                it = iter_packages(name=self.left_variant.name,
                                   paths=package_paths, range_=range_)
                diff_num = sum(1 for x in it) - 1

                unit = "version" if diff_num == 1 else "versions"
                icon_suffixes = {1: "_1", 2: "_2", 3: "_3"}
                icon_suffix = icon_suffixes.get(diff_num, "")

            if self.left_variant == self.right_variant:
                self.mode = "equal_to"
                self._set_color(0.7, 0.7, 0.7)
                widget = IconButton("equal_to", "packages are equal")
            elif self.left_variant.version == self.right_variant.version:
                # same version, but package is different. This can happen when
                # a local package is released which then hides a central package
                # of the same version
                self.mode = "equalish"
                self._set_color(1, 1, 0)
                widget = IconButton(
                    "equalish", "packages versions are equal, but package is different")
            elif self.left_variant.version > self.right_variant.version:
                self.mode = "greater_than"
                self._set_color(0, 1, 0)
                if self.comparable:
                    desc = "package is %d %s ahead" % (diff_num, unit)
                    widget = IconButton("greater_than" + icon_suffix, desc)
                else:
                    widget = IconButton("greater_than", "package is newer")
            else:
                self.mode = "less_than"
                self._set_color(1, 0, 0)
                if self.comparable:
                    desc = "package is %d %s behind" % (diff_num, unit)
                    widget = IconButton("less_than" + icon_suffix, desc)
                else:
                    widget = IconButton("less_than", "package is older")
        elif self.right_variant:
            self.side = "right"
            self.mode = "missing"
            self._set_color(1, 0, 0)
            widget = IconButton("missing", "package is missing")
        elif self.left_variant:
            self.side = "left"
            self.mode = "new"
            self._set_color(0, 1, 0)
            widget = IconButton("new", "package is new")

        if widget:
            create_pane([None, widget, None], True, compact=True,
                        parent_widget=self)
            widget.clicked.connect(self._clicked)

    def left(self):
        return (self.side in ("left", "both"))

    def right(self):
        return (self.side in ("right", "both"))

    def _clicked(self):
        if self.comparable:
            from rezgui.dialogs.VariantVersionsDialog import VariantVersionsDialog
            dlg = VariantVersionsDialog(self.context_model, self.left_variant,
                                        reference_variant=self.right_variant,
                                        parent=self)
            dlg.exec_()
        elif self.mode == "equal_to":
            QtWidgets.QMessageBox.information(
                self,
                "Equal Package",
                "The packages are equal")
        elif self.mode == "equalish":
            QtWidgets.QMessageBox.information(
                self,
                "Equal Version Package",
                "The package in the current resolve:\n(%s)\n\nis the same "
                "version as the package in the reference resolve:\n(%s)\n\n"
                "but is a different package."
                % (self.left_variant.uri, self.right_variant.uri))
        elif self.mode == "missing":
            QtWidgets.QMessageBox.information(
                self,
                "Missing Package",
                "The package is present in the reference resolve only")
        elif self.mode == "new":
            QtWidgets.QMessageBox.information(
                self,
                "New Package",
                "The package is present in the current resolve only")
        elif self.mode == "greater_than":
            QtWidgets.QMessageBox.information(
                self,
                "Newer Package",
                "The package in the current resolve:\n(%s)\n\nis newer than "
                "the package in the reference resolve (%s)"
                % (self.left_variant.uri, self.right_variant.uri))
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Older Package",
                "The package in the current resolve:\n(%s)\n\nis older than "
                "the package in the reference resolve (%s)"
                % (self.left_variant.uri, self.right_variant.uri))

    def _set_color(self, *c):
        f = 0.8
        col = self.palette().color(QtGui.QPalette.Active, QtGui.QPalette.Base)
        bg_c = (col.redF(), col.greenF(), col.blueF())
        bg_c = [x * f for x in bg_c]
        c = [x * (1 - f) for x in c]
        c = [x + y for x, y in zip(bg_c, c)]
        self.color = QtGui.QColor.fromRgbF(*c)


class CellDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(CellDelegate, self).__init__(parent)
        pal = self.parent().palette()
        col = pal.color(QtGui.QPalette.Active, QtGui.QPalette.Button)
        self.pen = QtGui.QPen(col)
        self.stale_color = QtGui.QColor("orange")
        self.stale_pen = QtGui.QPen(self.stale_color)
        self.stale_pen.setWidth(2)
        self.pen.setCosmetic(True)
        self.stale_pen.setCosmetic(True)

        self.path = QtGui.QPainterPath()
        self.path.moveTo(0, 0)
        self.path.cubicTo(0.6, 0, -0.2, 0.5, 1, 0.5)
        self.path.cubicTo(-0.2, 0.5, 0.6, 1, 0, 1)

        highlight_color = pal.color(QtGui.QPalette.Highlight)
        base_color = pal.color(QtGui.QPalette.Base)
        c1 = interp_color(highlight_color, base_color, 0.3)
        c2 = interp_color(highlight_color, base_color, 0.8)

        grad = QtGui.QLinearGradient(0, 1, 0, 0)
        grad.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
        grad.setColorAt(0, c1)
        grad.setColorAt(0.95, c2)
        grad.setColorAt(1, c1)
        self.highlight_brush = QtGui.QBrush(grad)

    def paint(self, painter, option, index):
        row = index.row()
        column = index.column()
        table = self.parent()
        cmp_widget = table.cellWidget(row, 2)
        stale = table.context_model.is_stale()
        rect = option.rect
        oldbrush = painter.brush()
        oldpen = painter.pen()
        pal = table.palette()

        def _setpen(to_stale):
            pen = self.stale_pen if stale and to_stale else self.pen
            painter.setPen(pen)

        # determine cell bg color and paint it
        selected_cells = set((x.row(), x.column()) for x in table.selectedIndexes())
        bg_color = None
        if (row, column) in selected_cells:
            bg_color = self.highlight_brush
        elif cmp_widget and \
                ((cmp_widget.left() and column == 1)
                 or (cmp_widget.right() and column == 3)):
            bg_color = cmp_widget.color
        else:
            bg_color = pal.color(QtGui.QPalette.Base)

        painter.fillRect(rect, bg_color)

        # draw grid lines
        r = (rect.topRight(), rect.bottomRight())
        b = (rect.bottomLeft(), rect.bottomRight() - QtCore.QPoint(1, 0))
        _setpen(column < 2)

        if column == 0:
            painter.drawLine(*r)
            _setpen(False)
            painter.drawLine(*b)
        elif column == 1:
            if not cmp_widget or not cmp_widget.left():
                painter.drawLine(*r)
            if row == table.rowCount() - 1:
                painter.drawLine(*b)
            else:
                if stale and row == 0:
                    painter.drawLine(rect.topLeft(), rect.topRight())
                _setpen(False)
                painter.drawLine(*b)
        elif column == 2:
            # draw the curvy bits in the comparison column
            draw_right_edge = True

            def _draw_path():
                painter.setRenderHints(QtGui.QPainter.Antialiasing, True)
                painter.drawPath(self.path)
                painter.resetTransform()
                painter.setRenderHints(QtGui.QPainter.Antialiasing, False)

            if cmp_widget:
                if cmp_widget.left():
                    painter.translate(rect.topLeft() - QtCore.QPoint(1, 0.5))
                    painter.scale(rect.width() / 2.5, rect.height())
                    _setpen(True)
                    if stale:
                        pen = QtGui.QPen(self.stale_color)
                        pen.setCosmetic(True)
                        pen.setWidthF(1.5)
                        painter.setPen(pen)
                    if (row, 1) in selected_cells:
                        painter.setBrush(self.highlight_brush)
                    elif cmp_widget.color:
                        painter.setBrush(QtGui.QBrush(cmp_widget.color))
                    _draw_path()
                    _setpen(False)
                if cmp_widget.right():
                    painter.translate(rect.topRight() - QtCore.QPoint(-1, 0.5))
                    painter.scale(-rect.width() / 2.5, rect.height())
                    if (row, 3) in selected_cells:
                        painter.setBrush(self.highlight_brush)
                    elif cmp_widget.color:
                        painter.setBrush(QtGui.QBrush(cmp_widget.color))
                    _draw_path()
                    draw_right_edge = False

            if draw_right_edge:
                painter.drawLine(*r)
        else:
            painter.drawLine(*r)
            painter.drawLine(*b)

        painter.setPen(oldpen)
        painter.setBrush(oldbrush)

        if cmp_widget and column in (1, 3):
            index = table.model().index(row, 2)
            table.update(index)


class ContextTableWidget(QtWidgets.QTableWidget, ContextViewMixin):

    default_row_count = 10
    double_arrow = u"\u27FA"
    short_double_arrow = u"\u21D4"
    variantSelected = QtCore.Signal(object)

    def __init__(self, context_model=None, parent=None):
        """Create a context table."""
        super(ContextTableWidget, self).__init__(self.default_row_count,
                                                 2, parent)
        ContextViewMixin.__init__(self, context_model)

        self.diff_mode = False
        self.diff_context_model = None
        self.diff_from_source = False
        self._show_effective_request = False
        self._current_variant = None

        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        hh = self.horizontalHeader()
        hh.setDefaultSectionSize(12 * self.fontMetrics().height())

        vh = self.verticalHeader()
        QtCompat.QHeaderView.setSectionResizeMode(
            vh, QtWidgets.QHeaderView.ResizeToContents)
        vh.setVisible(False)

        self.delegate = CellDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setShowGrid(False)

        self.currentCellChanged.connect(self._currentCellChanged)
        self.itemSelectionChanged.connect(self._itemSelectionChanged)
        self.refresh()

    def selectionCommand(self, index, event=None):
        row = index.row()
        column = index.column()

        widget = self.cellWidget(row, column)
        if self._widget_is_selectable(widget):
            return QtCore.QItemSelectionModel.ClearAndSelect
        else:
            return QtCore.QItemSelectionModel.Clear

    def current_variant(self):
        """Returns the currently selected variant, if any."""
        return self._current_variant

    def show_effective_request(self, b):
        if b != self._show_effective_request:
            self._show_effective_request = b
            self._update_request_column(0, self.context_model)
            if self.diff_mode:
                self._update_request_column(4, self.diff_context_model)

    def get_request(self):
        """Get the current request list.

        Returns:
            List of strings.
        """
        return self._get_request(0)

    def enter_diff_mode(self, context_model=None):
        """Enter diff mode.

        Args:
            context_model (`ContextModel`): Context to diff against. If None, a
            copy of the current context is used.
        """
        assert not self.diff_mode
        self.diff_mode = True

        if context_model is None:
            self.diff_from_source = True
            self.diff_context_model = self.context_model.copy()
        else:
            self.diff_from_source = False
            self.diff_context_model = context_model

        self.clear()
        self.setColumnCount(5)
        self.refresh()

    def leave_diff_mode(self):
        """Leave diff mode."""
        assert self.diff_mode
        self.diff_mode = False
        self.diff_context_model = None
        self.diff_from_source = False
        self.setColumnCount(2)
        self.refresh()

    def revert_to_diff(self):
        assert self.diff_mode
        source_context = self.diff_context_model.context()
        self.context_model.set_context(source_context)

    def revert_to_disk(self):
        filepath = self.context_model.filepath()
        assert filepath
        disk_context = app.load_context(filepath)
        self.context_model.set_context(disk_context)

    def get_title(self):
        """Returns a string suitable for titling a window containing this table."""
        def _title(context_model):
            context = context_model.context()
            if context is None:
                return "new context*"
            title = os.path.basename(context.load_path) if context.load_path \
                else "new context"
            if context_model.is_modified():
                title += '*'
            return title

        if self.diff_mode:
            diff_title = _title(self.diff_context_model)
            if self.diff_from_source:
                diff_title += "'"
            return "%s  %s  %s" % (_title(self.context_model),
                                   self.short_double_arrow, diff_title)
        else:
            return _title(self.context_model)

    # Stops focus loss when a widget inside the table is selected. In an MDI app
    # this can cause the current subwindow to lose focus.
    def clear(self):
        self.setFocus()
        super(ContextTableWidget, self).clear()

    def select_variant(self, name):
        for row, widget in self._iter_column_widgets(1, VariantCellWidget):
            if widget.variant.name == str(name):
                self.setCurrentIndex(self.model().index(row, 1))
                return

    def refresh(self):
        self._contextChanged(ContextModel.CONTEXT_CHANGED)

    def _contextChanged(self, flags=0):
        update_request_columns = {}

        # apply request and variant widgets to columns
        if flags & ContextModel.CONTEXT_CHANGED:
            self.clear()

            if self.diff_mode:
                hh = self.horizontalHeader()
                QtCompat.QHeaderView.setSectionResizeMode(
                    hh, 2, QtWidgets.QHeaderView.Fixed)
                self.setColumnWidth(2, 50)

            if self.context():
                if self.diff_mode:
                    self._apply_request(self.diff_context_model, 4)
                    self._apply_resolve(self.diff_context_model, 3, 4,
                                        hide_locks=True, read_only=True)
                    self._apply_request(self.context_model, 0)
                    self._apply_resolve(self.context_model, 1, 3,
                                        reference_column_is_variants=True)
                    self._update_comparison_column(2)
                    update_request_columns[4] = self.diff_context_model
                else:
                    self._apply_request(self.context_model, 0)
                    self._apply_resolve(self.context_model, 1, 0)
            else:
                self._set_package_cell(0, 0)
            update_request_columns[0] = self.context_model

        if flags & ContextModel.LOCKS_CHANGED and self._show_effective_request:
            update_request_columns[0] = self.context_model

        for column, context_model in update_request_columns.items():
            self._update_request_column(column, context_model)

        # set column headers
        if self.diff_mode:
            headers = [["current request", False],
                       ["current resolve", False],
                       [self.double_arrow, False],
                       ["reference resolve", True],
                       ["reference request", True]]
        else:
            headers = [["request", False],
                       ["resolve", False]]
        if self.context_model.is_stale():
            headers[0][0] += '*'
            headers[1][0] += " (stale)"
            headers[1][1] = True

        for column, (label, italic) in enumerate(headers):
            item = QtWidgets.QTableWidgetItem(label)
            update_font(item, italic=italic)
            self.setHorizontalHeaderItem(column, item)

        self.update()

    def _update_request_column(self, column, context_model):
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
            for lock, requests in d.items():
                for request in requests:
                    request_str = str(request)
                    self._set_effective_package_cell(row, column, request_str, lock.name)
                    row += 1

        self._trim_trailing_rows()

    def _widget_is_selectable(self, widget):
        return (widget
                and widget.isEnabled()
                and isinstance(widget, VariantCellWidget)
                and not widget.read_only)

    def _currentCellChanged(self, currentRow, currentColumn,
                            previousRow, previousColumn):
        widget = self.cellWidget(currentRow, currentColumn)
        if self._widget_is_selectable(widget):
            self._current_variant = widget.variant
        else:
            self._current_variant = None
            self.setCurrentIndex(QtCore.QModelIndex())

        # update other variants, this causes them to show/hide the depends icon
        if previousColumn != currentColumn:
            for _, widget in self._iter_column_widgets(previousColumn, VariantCellWidget):
                widget.set_reference_sibling(None)
        for _, widget in self._iter_column_widgets(currentColumn, VariantCellWidget):
            widget.set_reference_sibling(self._current_variant)

        # new selection is failing to cause a paint update sometimes?? This
        # seems to help but does not 100% fix the problem.
        self.update(self.model().index(previousRow, previousColumn))
        self.update(self.model().index(currentRow, currentColumn))

        self.variantSelected.emit(self._current_variant)

    # this is only here to clear the current index, which leaves an annoying
    # visual cue even though the cell is not selected
    def _itemSelectionChanged(self):
        if not self.selectedIndexes():
            self.setCurrentIndex(QtCore.QModelIndex())

    def _iter_column_widgets(self, column, types=None):
        types = types or QtWidgets.QWidget
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

    def _apply_resolve(self, context_model, column, reference_column,
                       hide_locks=False, read_only=False,
                       reference_column_is_variants=False):
        context = context_model.context()
        resolved = context.resolved_packages[:]
        consumed_rows = set()

        # match variants up with matching request/variant in source column
        for row, widget in self._iter_column_widgets(
                reference_column, (PackageSelectWidget, VariantCellWidget)):
            request_str = str(widget.text())
            if not request_str:
                continue

            package_name = Requirement(request_str).name
            matches = [x for x in resolved if x.name == package_name]
            if matches:
                variant = matches[0]
                resolved = [x for x in resolved if x.name != package_name]
                reference_variant = None
                if reference_column_is_variants and isinstance(widget, VariantCellWidget):
                    reference_variant = widget.variant
                self._set_variant_cell(row, column, context_model, variant,
                                       reference_variant=reference_variant,
                                       hide_locks=hide_locks, read_only=read_only)
            consumed_rows.add(row)

        # append variants that don't match reference requests/variants
        if reference_column_is_variants:
            hide_locks = True
        row = 0

        while resolved:
            variant = resolved[0]
            resolved = resolved[1:]
            while row in consumed_rows:
                row += 1
            self._set_variant_cell(row, column, context_model, variant,
                                   hide_locks=hide_locks, read_only=read_only)
            row += 1

    def _update_comparison_column(self, column):
        #no_color = self.palette().color(QtGui.QPalette.Active, QtGui.QPalette.Base)

        for row in range(self.rowCount()):
            left = self.cellWidget(row, column - 1)
            right = self.cellWidget(row, column + 1)
            left_variant = left.variant if left else None
            right_variant = right.variant if right else None
            if left_variant or right_variant:
                widget = CompareCell(self.context_model, left_variant, right_variant)
                self.setCellWidget(row, column, widget)

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
                          reference_variant=None, hide_locks=False,
                          read_only=False):
        if row >= self.rowCount():
            self.setRowCount(row + 1)

        widget = VariantCellWidget(context_model, variant,
                                   reference_variant=reference_variant,
                                   hide_locks=hide_locks, read_only=read_only)
        self.setCellWidget(row, column, widget)
        widget._set_stale(column != 1)

    def _set_cell_text(self, row, column, txt):
        if row >= self.rowCount():
            self.setRowCount(row + 1)

        if self.cellWidget(row, column):
            self.removeCellWidget(row, column)
        item = QtWidgets.QTableWidgetItem(txt)
        self.setItem(row, column, item)

    def _packageTextChanged(self, row, column, txt):
        if txt:
            if self._set_package_cell(row + 1, column):
                self._update_request_column(column, self.context_model)

    def _packageFocusOutViaKeyPress(self, row, column, txt):
        if txt:
            self._set_current_cell(row + 1, column)
        else:
            widget = self.cellWidget(row + 1, column)
            if widget and isinstance(widget, PackageSelectWidget):
                self._delete_cell(row, column)

            new_request = self.get_request()
            self.context_model.set_request(new_request)
            self._update_request_column(column, self.context_model)

    def _packageFocusOut(self, row, column, txt):
        if txt:
            self._set_package_cell(row + 1, column)
        else:
            widget = self.cellWidget(row + 1, column)
            if widget and isinstance(widget, PackageSelectWidget):
                self._delete_cell(row, column)

        new_request = self.get_request()
        self.context_model.set_request(new_request)
        self._update_request_column(column, self.context_model)

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


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
