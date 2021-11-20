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


from Qt import QtCore, QtWidgets, QtGui
from rezgui.objects.Config import Config
#from rezgui.objects.ProcessTrackerThread import ProcessTrackerThread
from rezgui import organisation_name, application_name
from rez.resolved_context import ResolvedContext
from rez.exceptions import ResolvedContextError
from rez.utils.data_utils import cached_property
from rez.vendor import yaml
from contextlib import contextmanager
import sys
import os.path
import os


class App(QtWidgets.QApplication):
    def __init__(self, argv=None):
        if argv is None:
            argv = sys.argv
        super(App, self).__init__(argv)
        self.setOrganizationName(organisation_name)
        self.setApplicationName(application_name)
        self.main_window = None

    @cached_property
    def config(self):
        filepath = os.path.dirname(__file__)
        filepath = os.path.dirname(filepath)
        filepath = os.path.join(filepath, "rezguiconfig")
        with open(filepath) as f:
            settings = yaml.load(f.read(), Loader=yaml.FullLoader)

        return Config(settings,
                      organization=organisation_name,
                      application=application_name)

    @cached_property
    def process_tracker(self):
        return None
        #th = ProcessTrackerThread()
        #th.start()
        #return th

    @contextmanager
    def status(self, txt):
        with self.main_window.status(txt):
            yield

    def set_main_window(self, window):
        self.main_window = window

    def load_context(self, filepath):
        context = None
        busy_cursor = QtGui.QCursor(QtCore.Qt.WaitCursor)

        with self.status("Loading %s..." % filepath):
            QtWidgets.QApplication.setOverrideCursor(busy_cursor)
            try:
                context = ResolvedContext.load(filepath)
            except ResolvedContextError as e:
                QtWidgets.QMessageBox.critical(self.main_window,
                                           "Failed to load context", str(e))
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()

        if context:
            path = os.path.realpath(filepath)
            self.config.prepend_string_list("most_recent_contexts", path,
                                            "max_most_recent_contexts")
        return context

    def execute_shell(self, context, command=None, terminal=False, **Popen_args):

        # if the gui was called from a rez-env'd environ, then the new shell
        # here will have a prompt like '>>'. It's not incorrect, but it is a
        # bit misleading, from this floating shell you can't exit back into the
        # calling rez environ. So here we force back to '>'.
        #
        env = os.environ.copy()
        if "REZ_ENV_PROMPT" in env:
            del env["REZ_ENV_PROMPT"]

        return context.execute_shell(command=command,
                                     block=False,
                                     detached=terminal,
                                     parent_environ=env,
                                     start_new_session=True,
                                     **Popen_args)

# app singleton
app = App()
