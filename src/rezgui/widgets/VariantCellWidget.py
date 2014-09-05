from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, get_icon_widget, add_locking_submenu, \
    add_menu_action, update_font
from rezgui.models.ContextModel import ContextModel
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rez.packages import iter_packages
from rez.resolved_context import PatchLock
from rez.vendor.version.requirement import RequirementList


class VariantCellWidget(QtGui.QWidget, ContextViewMixin):
    def __init__(self, context_model, variant, parent=None):
        super(VariantCellWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

        self.variant = variant
        self.stale = False
        self.lock_status = None
        self.lock_icon = None
        self.icons = []  # 3-tuples: widget, name, tooltip

        self.label = QtGui.QLabel(self.variant.qualified_package_name)
        if self.variant.description:
            self.label.setToolTip(self.variant.description)

        self.layout = QtGui.QHBoxLayout()
        self.layout.setSpacing(2)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.addWidget(self.label, 1)
        self.setLayout(self.layout)

        self.refresh()

    def contextMenuEvent(self, event):
        menu = QtGui.QMenu(self)
        _, actions = add_locking_submenu(menu, self._set_lock_type)
        lock = self.context_model.get_patch_lock(self.variant.name)
        if lock is not None:
            actions[lock].setChecked(True)

        action = add_menu_action(menu, "Remove Lock", self._remove_lock)
        action.setEnabled(lock is not None)

        menu.exec_(self.mapToGlobal(event.pos()))
        menu.setParent(None)

    def refresh(self):
        self._contextChanged(ContextModel.CONTEXT_CHANGED)

    def _contextChanged(self, flags=0):
        self._set_stale(self.context_model.is_stale())

        if flags & (ContextModel.PACKAGES_PATH_CHANGED |
                    ContextModel.CONTEXT_CHANGED):
            # update icons
            new_icons = []

            if self.variant.index is not None:
                package = self.variant.parent
                if package.num_variants > 1:
                    txt = "1 of %d variants" % package.num_variants
                    new_icons.append(("variant", txt))

            if self.variant.is_local:
                new_icons.append(("local", "package is local"))

            package_paths = self.context_model.packages_path
            if self.variant.search_path in package_paths:
                packages = None
                try:
                    it = iter_packages(name=self.variant.name, paths=package_paths)
                    packages = sorted(it, key=lambda x: x.version)
                except:
                    pass
                if packages:
                    # test if variant is latest package
                    latest_pkg = packages[-1]
                    if self.variant.version == latest_pkg.version:
                        new_icons.append(("green_tick", "package is latest"))
                    else:
                        # test if variant is in request, and is latest possible
                        range_ = None
                        try:
                            request = self.context().requested_packages(True)
                            reqlist = RequirementList(request)
                            if self.variant.name in reqlist.names:
                                range_ = reqlist.get(self.variant.name).range
                        except:
                            pass
                        if range_ is not None:
                            packages = [x for x in packages if x.version in range_]
                            if packages:
                                latest_pkg = packages[-1]
                                if self.variant.version == latest_pkg.version:
                                    new_icons.append(("yellow_tick",
                                                      "package is latest within request"))
            else:
                new_icons.append(("error", "package is not in the search path"))

            self._set_icons(new_icons)

        if flags & (ContextModel.LOCKS_CHANGED |
                    ContextModel.CONTEXT_CHANGED):
            # update lock icon
            lock = self.context_model.get_patch_lock(self.variant.name)
            if lock is None:
                lock = self.context_model.default_patch_lock
                icon_name = "%s_faint" % lock.name
            else:
                icon_name = lock.name
            self._set_lock_icon(icon_name, lock.description.lower())

    def _set_lock_type(self, lock_type):
        self.context_model.set_patch_lock(self.variant.name, lock_type)

    def _remove_lock(self):
        self.context_model.remove_patch_lock(self.variant.name)

    def _set_stale(self, b=True):
        if b != self.stale:
            update_font(self.label, italic=b)
            self.label.setEnabled(not b)
            self.stale = b

    def _set_icons(self, icons):
        current_icons = [tuple(x[1:]) for x in self.icons]
        if icons == current_icons:
            return

        for t in self.icons:
            widget = t[0]
            self.layout.removeWidget(widget)
            widget.setParent(None)
        self.icons = []

        for name, tooltip in icons:
            widget = get_icon_widget(name, tooltip)
            self.layout.addWidget(widget)
            self.icons.append((widget, name, tooltip))

    def _set_lock_icon(self, name, tooltip):
        if self.lock_icon:
            widget_, name_, tooltip_ = self.lock_icon
            if name == name_:
                return
            self.layout.removeWidget(widget_)
            widget_.setParent(None)

        widget = get_icon_widget(name, tooltip)
        self.layout.insertWidget(0, widget)
        self.lock_icon = (widget, name, tooltip)
