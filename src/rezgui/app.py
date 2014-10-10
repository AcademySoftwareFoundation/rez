from rezgui.objects.App import app
from rezgui.windows.MainWindow import MainWindow
import os.path
import sys


def run(opts=None, parser=None):
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
    app.set_main_window(main_window)
    main_window.show()

    for filepath in context_files:
        main_window.open_context(filepath)
    main_window.cascade()

    sys.exit(app.exec_())
