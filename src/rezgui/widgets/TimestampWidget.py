from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane
from rezgui.widgets.IconButton import IconButton
from rezgui.dialogs.BrowsePackageDialog import BrowsePackageDialog


class TimestampWidget(QtGui.QFrame):
    def __init__(self, context_model, parent=None):
        super(TimestampWidget, self).__init__(parent)
        self.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Sunken)
        self.context_model = context_model

        self.package_btn = IconButton("package")
        self.checkbox = QtGui.QCheckBox("ignore packages released after...")
        pane = create_pane([None, self.checkbox, self.package_btn], True, compact=True)

        self.edit = QtGui.QDateTimeEdit()
        self.edit.setCalendarPopup(True)
        self.edit.setDateTime(QtCore.QDateTime.currentDateTime())

        create_pane([pane, self.edit], False, compact=True, parent_widget=self)
        self.checkbox.stateChanged.connect(self._stateChanged)
        self.package_btn.clicked.connect(self._selectPackage)

        self.refresh()

    def refresh(self):
        b = self.checkbox.isChecked()
        self.package_btn.setEnabled(b)
        self.edit.setEnabled(b)

    def _stateChanged(self, state):
        self.refresh()

    def _selectPackage(self):
        fn = lambda x: bool(x.timestamp)
        dlg = BrowsePackageDialog(context_model=self.context_model,
                                  parent=self.parentWidget(),
                                  package_selectable_callback=fn)
        dlg.exec_()
        if dlg.package:
            dt = QtCore.QDateTime()
            dt.setTime_t(dlg.package.timestamp)
            self.edit.setDateTime(dt)
