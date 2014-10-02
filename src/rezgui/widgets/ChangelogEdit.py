from rezgui.qt import QtCore, QtGui
import cgi


def plaintext_to_html(txt):
    out = cgi.escape(txt)
    out = out.replace('\t', "    ")
    out = out.replace(' ', "&nbsp;")
    out = out.replace('\n', "<br>")
    return out


class ChangelogEdit(QtGui.QPlainTextEdit):
    def __init__(self, parent=None):
        super(ChangelogEdit, self).__init__(parent)
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)

    def set_packages(self, packages):
        self.clear()
        lines = []

        # note - I'm not just using appendHtml()/appendPlainText, because there's
        # a qt bug causing this to mess up the formatting. Hence the need to
        # convert plaintext to html manually.

        for package in packages:
            heading = str(package.version)
            body = (package.changelog or "-").strip()
            body = plaintext_to_html(body)
            html = ("<p><font size='+2'><b>%s</b></font><br>%s<br></p>"
                    % (heading, body))
            lines.append(html)

        self.appendHtml(''.join(lines))
        self.moveCursor(QtGui.QTextCursor.Start)
