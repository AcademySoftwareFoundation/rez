import sys
from rezgui import organisation_name, application_name
from rezgui.qt import QtGui
from rezgui.dialogs.test_dialog import TestDialog


def run():
    app = QtGui.QApplication(sys.argv)
    app.setOrganizationName(organisation_name)
    app.setApplicationName(application_name)

    w = TestDialog()
    w.exec_()
