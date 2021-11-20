# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
