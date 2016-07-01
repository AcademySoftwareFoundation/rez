from rezgui.objects.App import app
from rezgui.windows.MainWindow import MainWindow
import os.path
import sys


def get_context_files(filepaths):
    context_files = []

    for path in filepaths:
        if os.path.exists(path):
            if os.path.isfile(path):
                context_files.append(os.path.abspath(path))
            else:
                raise IOError("Not a file: %s" % path)
        else:
            open(path)  # raise IOError

    return context_files


def run(opts=None, parser=None):
    main_window = MainWindow()
    app.set_main_window(main_window)
    main_window.show()

    if opts.diff:
        # open context in diff mode against another
        context_files = get_context_files(opts.diff)
        subwindow = main_window.open_context_and_diff_with_file(*context_files)

        if subwindow:
            subwindow.showMaximized()
    else:
        # open contexts
        context_files = get_context_files(opts.FILE or [])
        for filepath in context_files:
            subwindow = main_window.open_context(filepath)

        if len(context_files) == 1:
            subwindow.showMaximized()
        else:
            main_window.cascade()

    sys.exit(app.exec_())


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
