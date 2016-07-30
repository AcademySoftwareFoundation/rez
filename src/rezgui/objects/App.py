from rezgui.qt import QtCore, QtGui
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


class App(QtGui.QApplication):
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
            settings = yaml.load(f.read())

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
            QtGui.QApplication.setOverrideCursor(busy_cursor)
            try:
                context = ResolvedContext.load(filepath)
            except ResolvedContextError as e:
                QtGui.QMessageBox.critical(self.main_window,
                                           "Failed to load context", str(e))
            finally:
                QtGui.QApplication.restoreOverrideCursor()

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
