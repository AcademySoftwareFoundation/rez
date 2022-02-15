# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from Qt import QtCore, QtWidgets, QtGui
import cgi


def plaintext_to_html(txt):
    out = cgi.escape(txt)
    out = out.replace('\t', "    ")
    out = out.replace(' ', "&nbsp;")
    out = out.replace('\n', "<br>")
    return out


class ChangelogEdit(QtWidgets.QPlainTextEdit):
    def __init__(self, parent=None):
        super(ChangelogEdit, self).__init__(parent)
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)

    def set_packages(self, packages):
        # note - I'm not just using appendHtml()/appendPlainText, because there's
        # a qt bug causing this to mess up the formatting. Hence the need to
        # convert plaintext to html manually.

        lines = []
        for package in packages:
            heading = str(package.version)
            body = (package.changelog or "-").strip()
            body = plaintext_to_html(body)
            html = ("<p><font size='+2'><b>%s</b></font><br>%s<br></p>"
                    % (heading, body))
            lines.append(html)

        busy_cursor = QtGui.QCursor(QtCore.Qt.WaitCursor)
        QtWidgets.QApplication.setOverrideCursor(busy_cursor)
        try:
            self.clear()
            self.appendHtml(''.join(lines))
            self.moveCursor(QtGui.QTextCursor.Start)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()


class VariantChangelogEdit(ChangelogEdit):
    def __init__(self, parent=None):
        super(VariantChangelogEdit, self).__init__(parent)
        self.variant = None

    def set_variant(self, variant):
        if variant is None:
            self.clear()
        else:
            self.set_packages([variant])

        self.variant = variant
