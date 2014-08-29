from rezgui.qt import QtGui
from rezgui.objects.Config import Config
from rezgui.objects.ProcessTrackerThread import ProcessTrackerThread
from rezgui import organisation_name, application_name
from rez.util import propertycache
from rez.vendor import yaml
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

    @propertycache
    def config(self):
        filepath = os.path.dirname(__file__)
        filepath = os.path.dirname(filepath)
        filepath = os.path.join(filepath, "rezguiconfig")
        with open(filepath) as f:
            settings = yaml.load(f.read())

        return Config(settings,
                      organization=organisation_name,
                      application=application_name)

    @propertycache
    def process_tracker(self):
        th = ProcessTrackerThread()
        th.start()
        return th

    def execute_shell(self, context, command=None, terminal=False):

        # if the gui was called from a rez-env'd environ, then the new shell
        # here will have a prompt like '>>'. It's not incorrect, but it is a
        # bit misleading, from this floating shell you can't exit back into the
        # calling rez environ.
        env = os.environ.copy()
        if "REZ_ENV_PROMPT" in env:
            del env["REZ_ENV_PROMPT"]

        term_cmd = self.config.get("terminal_command") if terminal else None
        proc = context.execute_shell(command=command,
                                     block=False,
                                     pre_command=term_cmd,
                                     parent_environ=env,
                                     start_new_session=True)

# app singleton
app = App()
