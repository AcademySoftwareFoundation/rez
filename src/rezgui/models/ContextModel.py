from rezgui.qt import QtCore
from rez.resolved_context import ResolvedContext, PatchLock
from rez.config import config


class ContextModel(QtCore.QObject):
    """A model of a `ResolvedContext` object.

    Note that this is NOT a QAbstractItemModel subclass! A context does not lend
    itself to this data structure unfortunately.

    This model not only represents a context, but also contains the settings
    needed to create a new context, or re-resolve an existing context.
    """
    dataChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super(ContextModel, self).__init__(parent)

        self._context = None
        self._stale = True

        self.request_strings = []
        self.packages_path = config.packages_path
        self.implicit_packages = config.implicit_packages
        self.default_patch_lock = PatchLock.no_lock

    def is_stale(self):
        """Returns True if the context is stale.

        If the context is stale, this means there are pending changes. To update
        the model, you should call create_context() to build a new context with
        the current settings, and then set this context using set_context().
        """
        return self._stale

    def context(self):
        """Return the current context, if any."""
        return self._context

    def set_request(self, request_strings):
        self.request_strings = request_strings[:]
        self._changed()

    def set_packages_path(self, packages_path):
        self.packages_path = packages_path
        self._changed()

    def set_default_patch_lock(self, lock):
        self.default_patch_lock = lock
        self._changed()

    def create_context(self, verbosity=0, callback=None, buf=None,
                       package_load_callback=None):
        """Create a new context using the current settings.

        If a context already exists, then we are performing a 'patch' - ie, we
        are using the current settings, plus the previous context, to build the
        new context.

        Returns:
            `ResolvedContext` object.
        """
        return ResolvedContext(
            self.request_strings,
            package_paths=self.packages_path,
            verbosity=verbosity,
            buf=buf,
            callback=callback,
            package_load_callback=package_load_callback)

    def set_context(self, context):
        """Set the current context."""
        self._context = context
        self._stale = False

        self.request_strings = [str(x) for x in context.requested_packages()]
        self.packages_path = context.packages_path
        self.implicit_packages = context.implicit_packages
        self.default_patch_lock = context.default_patch_lock
        self.dataChanged.emit()

    def can_revert(self):
        """Return True if the model is revertable, False otherwise."""
        return bool(self._stale and self._context)

    def revert(self):
        """Discard any pending changes."""
        assert self.can_revert()
        self.set_context(self._context)

    def _changed(self):
        self._stale = True
        self.dataChanged.emit()
