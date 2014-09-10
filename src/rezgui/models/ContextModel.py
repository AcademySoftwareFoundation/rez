from rezgui.qt import QtCore
from rez.resolved_context import ResolvedContext, PatchLock, get_lock_request
from rez.config import config
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

    def __init__(self, context=None, parent=None):
        super(ContextModel, self).__init__(parent)

        self._context = None
        self._stale = True

        self.request = []
        self.packages_path = config.packages_path
        self.implicit_packages = config.implicit_packages
        self.default_patch_lock = PatchLock.no_lock
        self.patch_locks = {}

        if context:
            self._set_context(context)

    def copy(self):
        """Returns a copy of the context."""
        other = ContextModel(self._context, self.parent())
        other._stale = self._stale
        other.request = self.request[:]
        other.packages_path = self.packages_path
        other.implicit_packages = self.implicit_packages
        other.default_patch_lock = self.default_patch_lock
        other.patch_locks = copy.deepcopy(self.patch_locks)
        return other

    def is_stale(self):
        """Returns True if the context is stale.

        If the context is stale, this means there are pending changes. To update
        the model, you should call resolve_context().
        """
        return self._stale

    def context(self):
        """Return the current context, if any."""
        return self._context

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
        self._changed("request", request_strings, self.REQUEST_CHANGED)

    def set_packages_path(self, packages_path):
        self._changed("packages_path", packages_path, self.PACKAGES_PATH_CHANGED)

    def set_default_patch_lock(self, lock):
        self._changed("default_patch_lock", lock, self.LOCKS_CHANGED)

    def set_patch_lock(self, package_name, lock):
        existing_lock = self.patch_locks.get(package_name)
        if lock != existing_lock:
            self.patch_locks[package_name] = lock
            self._stale = True
            self.dataChanged.emit(self.LOCKS_CHANGED)

    def remove_patch_lock(self, package_name):
        if package_name in self.patch_locks:
            del self.patch_locks[package_name]
            self._stale = True
            self.dataChanged.emit(self.LOCKS_CHANGED)

    def remove_all_patch_locks(self):
        if self.patch_locks:
            self.patch_locks = {}
            self._stale = True
            self.dataChanged.emit(self.LOCKS_CHANGED)

    def resolve_context(self, verbosity=0, max_fails=-1, timestamp=None,
                        callback=None, buf=None, package_load_callback=None):
        """Update the current context by performing a re-resolve.

        The newly resolved context is only applied if it is a successful solve.

        Returns:
            `ResolvedContext` object, which may be a successful or failed solve.
        """
        context = ResolvedContext(
            self.request,
            package_paths=self.packages_path,
            verbosity=verbosity,
            max_fails=max_fails,
            timestamp=timestamp,
            buf=buf,
            callback=callback,
            package_load_callback=package_load_callback)

        if context.success:
            self._set_context(context)
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
        self._set_context(context)

    def _set_context(self, context):
        self._context = context
        self._stale = False

        self.request = [str(x) for x in context.requested_packages()]
        self.packages_path = context.package_paths
        self.implicit_packages = context.implicit_packages[:]
        self.default_patch_lock = context.default_patch_lock
        self.patch_locks = copy.deepcopy(context.patch_locks)

        self.dataChanged.emit(self.CONTEXT_CHANGED |
                              self.REQUEST_CHANGED |
                              self.PACKAGES_PATH_CHANGED |
                              self.LOCKS_CHANGED)

    def _changed(self, attr, value, flags):
        if getattr(self, attr) == value:
            return
        self._stale = True
        setattr(self, attr, value)
        self.dataChanged.emit(flags)
