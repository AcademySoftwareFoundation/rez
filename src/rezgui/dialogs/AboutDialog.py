# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from Qt import QtCore, QtWidgets
from rezgui.util import create_pane, get_icon
from rez import __version__
from rez.vendor.version.version import Version


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        self.setWindowTitle("About Rez")

        version = Version(__version__)
        public_version = version.trim(2)

        label = QtWidgets.QLabel(
            "<font size='+2'><b>Rez version %s</b></font><br><br>"
            "Build version %s."
            % (str(public_version), str(version)))

        close_btn = QtWidgets.QPushButton("Close")
        github_btn = QtWidgets.QPushButton("Github")
        github_icon = get_icon("github_32", as_qicon=True)
        github_btn.setIcon(github_icon)

        btn_pane = create_pane([None, github_btn, close_btn], True, compact=True)
        create_pane([label, None, btn_pane], False, parent_widget=self)

        github_btn.clicked.connect(self._goto_github)
        close_btn.clicked.connect(self.close)
        close_btn.setFocus()

    def sizeHint(self):
        return QtCore.QSize(300, 150)

    def _goto_github(self):
        import webbrowser
        webbrowser.open_new("https://github.com/nerdvegas/rez")
