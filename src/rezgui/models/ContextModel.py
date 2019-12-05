from Qt import QtCore
from rez.resolved_context import ResolvedContext, PatchLock, get_lock_request
from rez.package_filter import PackageFilterList
from rez.config import config
from rez.vendor.pygraph.algorithms.accessibility import accessibility
from collections import defaultdict
import copy


class ContextModel(QtCore.QObject):
    """A model of a `ResolvedContext` object.

    Note that this is NOT a QAbstractItemModel subclass! A context does not lend
    itself to this data structure unfortunately.

    This model not only represents a context, but also contains the settings
    needed to create a new context, or re-resolve an existing context.
    """
    dataChanged = QtCore.Signal(int)

    # dataChanged flags
    REQUEST_CHANGED = 1
    PACKAGES_PATH_CHANGED = 2
    LOCKS_CHANGED = 4
    CONTEXT_CHANGED = 8
    LOADPATH_CHANGED = 16
    PACKAGE_FILTER_CHANGED = 32
    CACHING_CHANGED = 64

    def __init__(self, context=None, parent=None):
        super(ContextModel, self).__init__(parent)

        self._context = None
        self._stale = True
        self._modified = True
        self._dependency_graph = None
        self._dependency_lookup = None

        self.request = []
        self.packages_path = config.packages_path
        self.implicit_packages = config.implicit_packages
        self.package_filter = config.package_filter
        self.caching = config.resolve_caching
        self.default_patch_lock = PatchLock.no_lock
        self.patch_locks = {}

        if context:
            self._set_context(context)
            self._modified = False

    def copy(self):
        """Returns a copy of the context."""
        other = ContextModel(self._context, self.parent())
        other._stale = self._stale
        other._modified = self._modified
        other.request = self.request[:]
        other.packages_path = self.packages_path
        other.implicit_packages = self.implicit_packages
        other.package_filter = self.package_filter
        other.caching = self.caching
        other.default_patch_lock = self.default_patch_lock
        other.patch_locks = copy.deepcopy(self.patch_locks)
        return other

    def is_stale(self):
        """Returns True if the context is stale.

        If the context is stale, this means there are pending changes. To update
        the model, you should call resolve_context().
        """
        return self._stale

    def is_modified(self):
        """Returns True if the context has been changed since save/load, False
        otherwise.

        If the context has never been saved, True is always returned.
        """
        return self._modified

    def package_depends_on(self, name_a, name_b):
        """Returns dependency information about two packages:

            0: A does not depend, directly or indirectly, on B;
            1: A depends indirectly on B;
            2: A depends directly on B.
        """
        assert self._context
        if self._dependency_lookup is None:
            self._dependency_graph = self._context.get_dependency_graph()
            self._dependency_lookup = accessibility(self._dependency_graph)

        downstream = self._dependency_lookup.get(name_a, [])
        accessible = (name_b in downstream)
        if accessible:
            neighbours = self._dependency_graph.neighbors(name_a)
            return 2 if name_b in neighbours else 1
        else:
            return 0

    def context(self):
        """Return the current context, if any."""
        return self._context

    def filepath(self):
        """Return the path the current context was saved/loaded to, if any."""
        return self._context.load_path if self._context else None

    def get_patch_lock(self, package_name):
        """Return the patch lock associated with the package, or None."""
        return self.patch_locks.get(package_name)

    def get_lock_requests(self):
        """Take the current context, and the current patch locks, and determine
        the effective requests that will be added to the main request.

        Returns:
            A dict of (PatchLock, [Requirement]) tuples. Each requirement will be
            a weak package reference. If there is no current context, an empty
            dict will be returned.
        """
        d = defaultdict(list)
        if self._context:
            for variant in self._context.resolved_packages:
                name = variant.name
                version = variant.version
                lock = self.patch_locks.get(name)
                if lock is None:
                    lock = self.default_patch_lock

                request = get_lock_request(name, version, lock)
                if request is not None:
                    d[lock].append(request)
        return d

    def set_request(self, request_strings):
        self._attr_changed("request", request_strings, self.REQUEST_CHANGED)

    def set_packages_path(self, packages_path):
        self._attr_changed("packages_path", packages_path, self.PACKAGES_PATH_CHANGED)

    def set_package_filter(self, package_filter):
        self._attr_changed("package_filter", package_filter, self.PACKAGE_FILTER_CHANGED)

    def set_caching(self, caching):
        self._attr_changed("caching", caching, self.CACHING_CHANGED)

    def save(self, filepath):
        assert self._context
        assert not self._stale
        self._context.save(filepath)
        self._context.set_load_path(filepath)
        self._modified = False
        self.dataChanged.emit(self.LOADPATH_CHANGED)

    def set_default_patch_lock(self, lock):
        self._attr_changed("default_patch_lock", lock, self.LOCKS_CHANGED)

    def set_patch_lock(self, package_name, lock):
        existing_lock = self.patch_locks.get(package_name)
        if lock != existing_lock:
            self.patch_locks[package_name] = lock
            self._changed(self.LOCKS_CHANGED)

    def remove_patch_lock(self, package_name):
        if package_name in self.patch_locks:
            del self.patch_locks[package_name]
            self._changed(self.LOCKS_CHANGED)

    def remove_all_patch_locks(self):
        if self.patch_locks:
            self.patch_locks = {}
            self._changed(self.LOCKS_CHANGED)

    def resolve_context(self, verbosity=0, max_fails=-1, timestamp=None,
                        callback=None, buf=None, package_load_callback=None):
        """Update the current context by performing a re-resolve.

        The newly resolved context is only applied if it is a successful solve.

        Returns:
            `ResolvedContext` object, which may be a successful or failed solve.
        """
        package_filter = PackageFilterList.from_pod(self.package_filter)

        context = ResolvedContext(
            self.request,
            package_paths=self.packages_path,
            package_filter=package_filter,
            verbosity=verbosity,
            max_fails=max_fails,
            timestamp=timestamp,
            buf=buf,
            callback=callback,
            package_load_callback=package_load_callback,
            caching=self.caching)

        if context.success:
            if self._context and self._context.load_path:
                context.set_load_path(self._context.load_path)
            self._set_context(context)
            self._modified = True
        return context

    def can_revert(self):
        """Return True if the model is revertable, False otherwise."""
        return bool(self._stale and self._context)

    def revert(self):
        """Discard any pending changes."""
        if self.can_revert():
            self._set_context(self._context)

    def set_context(self, context):
        """Replace the current context with another."""
        self._set_context(context, emit=False)
        self._modified = (not context.load_path)
        self.dataChanged.emit(self.CONTEXT_CHANGED |
                              self.REQUEST_CHANGED |
                              self.PACKAGES_PATH_CHANGED |
                              self.LOCKS_CHANGED |
                              self.LOADPATH_CHANGED |
                              self.PACKAGE_FILTER_CHANGED |
                              self.CACHING_CHANGED)

    def _set_context(self, context, emit=True):
        self._context = context
        self._stale = False
        self._dependency_lookup = None

        self.request = [str(x) for x in context.requested_packages()]
        self.packages_path = context.package_paths
        self.implicit_packages = context.implicit_packages[:]
        self.package_filter = context.package_filter.to_pod()
        self.caching = context.caching
        self.default_patch_lock = context.default_patch_lock
        self.patch_locks = copy.deepcopy(context.patch_locks)
        if emit:
            self.dataChanged.emit(self.CONTEXT_CHANGED |
                                  self.REQUEST_CHANGED |
                                  self.PACKAGES_PATH_CHANGED |
                                  self.LOCKS_CHANGED)

    def _changed(self, flags):
        self._stale = True
        self._modified = True
        self.dataChanged.emit(flags)

    def _attr_changed(self, attr, value, flags):
        if getattr(self, attr) == value:
            return
        setattr(self, attr, value)
        self._changed(flags)


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
