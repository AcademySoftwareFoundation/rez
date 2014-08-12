import sys
from rezgui.qt import QtGui
from rezgui.dialogs.test_dialog import TestDialog


def run():
    app = QtGui.QApplication(sys.argv)
    w = TestDialog()
    w.exec_()
