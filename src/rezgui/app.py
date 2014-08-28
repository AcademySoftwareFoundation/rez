from rezgui.objects.App import app
from rezgui.windows.MainWindow import MainWindow
#from rezgui.dialogs.test_dialog import TestDialog
import os.path
import sys


def run(opts=None, parser=None):
    #w = TestDialog()
    #w.exec_()

    context_files = []
    for path in (opts.FILE or []):
        if os.path.exists(path):
            if os.path.isfile(path):
                context_files.append(path)
            else:
                pass  # TODO: suites
        else:
            open(path)  # raise IOError

    main_window = MainWindow()
    main_window.show()
    for filepath in context_files:
        main_window.load_context(filepath)
    main_window.cascade()

    sys.exit(app.exec_())
