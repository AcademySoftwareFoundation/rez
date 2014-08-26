from rezgui.qt import QtGui
from rezgui.objects.Config import Config
from rezgui.objects.ProcessTrackerThread import ProcessTrackerThread
from rezgui import organisation_name, application_name
from rez.util import propertycache
from rez.vendor import yaml
import sys
import os.path


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


# app singleton
app = App()
