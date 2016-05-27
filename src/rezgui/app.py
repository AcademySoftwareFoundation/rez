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


# Copyright 2016 Allan Johns.
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
