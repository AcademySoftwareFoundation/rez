# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
