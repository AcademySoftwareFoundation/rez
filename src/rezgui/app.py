from rezgui.objects.App import app
from rezgui.dialogs.test_dialog import TestDialog


def run():
    w = TestDialog()
    w.exec_()
