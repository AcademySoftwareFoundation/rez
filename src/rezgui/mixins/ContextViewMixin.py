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
