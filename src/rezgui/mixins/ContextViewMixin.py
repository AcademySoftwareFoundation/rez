# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from Qt import QtCore
from rezgui.models.ContextModel import ContextModel


class ContextViewMixin(object):
    """Context view class mixin. Eg:

        class MyContextView(QWidget, ContextViewMixin):
            def __init__(self, context_model):
                super(MyContextView, self).__init__()
                ContextViewMixin.__init__(self, context_model)
                # ... setup class ...
                self.child_view = MyContextView(self.context_model)

            def _contextChanged(self, flags=0):
                # handle the context update
    """
    def __init__(self, context_model=None):
        assert isinstance(self, QtCore.QObject)
        self.context_model = context_model or ContextModel()
        self._connect(True)

    def context(self):
        return self.context_model.context()

    def set_context_model(self, context_model=None):
        self._connect(False)
        self.context_model = context_model or ContextModel()
        self._connect(True)

    def _connect(self, b):
        if hasattr(self, "_contextChanged"):
            sig = self.context_model.dataChanged
            fn = sig.connect if b else sig.disconnect
            fn(self._contextChanged)
