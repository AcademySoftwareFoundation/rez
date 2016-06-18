from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane
from rezgui.objects.LoadPackagesThread import LoadPackagesThread
from functools import partial


class PackageLoadingWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(PackageLoadingWidget, self).__init__(parent)
        self.main_widget = None
        self.worker = None
        self.swap_delay = 0
        self.threads = []

        self.timer = None

        label = QtGui.QLabel("Loading Packages...")
        self.bar = QtGui.QProgressBar()
        self.loading_widget = create_pane([label, self.bar, None], False, compact=True)

        create_pane([self.loading_widget], True, compact=True, compact_spacing=0,
                    parent_widget=self)

    def set_packages(self, packages):
        """Implement this function in your subclass. It is called after packages
        are loaded, and the main widget will be bought into view afterwards."""
        raise NotImplementedError

    def set_loader_swap_delay(self, msecs):
        """Set the delay before widget swaps to show the loading bar. A delay is
        useful because it avoids the annoying flicker that results from a fast
        packages load."""
        self.swap_delay = msecs

    def set_main_widget(self, widget):
        layout = self.layout()
        if self.main_widget is not None:
            layout.removeWidget(self.main_widget)
            self.main_widget.setParent(None)

        layout.addWidget(widget)
        self.main_widget = widget
        self.loading_widget.hide()

    def stop_loading_packages(self):
        if self.worker:
            self.worker.stop()
            self.worker = None

    def load_packages(self, package_paths, package_name, range_=None,
                      package_attributes=None, callback=None):
        self.stop_loading_packages()
        self.bar.setRange(0, 0)

        self.worker = LoadPackagesThread(package_paths=package_paths,
                                         package_name=package_name,
                                         range_=range_,
                                         package_attributes=package_attributes,
                                         callback=callback)
        id_ = id(self.worker)
        self.worker.progress.connect(partial(self._progress, id_))
        self.worker.finished.connect(partial(self._packagesLoaded, id_))

        thread = QtCore.QThread()
        self.worker.moveToThread(thread)
        thread.started.connect(self.worker.run)

        threads = [(thread, self.worker)]
        for th, worker in self.threads:
            if th.isRunning():
                threads.append((th, worker))
        self.threads = threads

        if self.swap_delay == 0:
            self.loading_widget.show()
            if self.main_widget is not None:
                self.main_widget.hide()
        else:
            self.timer = QtCore.QTimer()
            self.timer.setSingleShot(True)
            self.timer.setInterval(self.swap_delay)
            fn = partial(self._swap_to_loader, id_)
            self.timer.timeout.connect(fn)
            self.timer.start()

        thread.start()

    def __del__(self):
        for _, worker in self.threads:
            worker.stop()
        for th, _ in self.threads:
            th.quit()
            th.wait()

    def _swap_to_loader(self, id_):
        if self.worker is None or id(self.worker) != id_:
            return

        self.loading_widget.show()
        if self.main_widget is not None:
            self.main_widget.hide()

    def _progress(self, id_, value, total):
        if self.worker is None or id(self.worker) != id_:
            return

        self.bar.setMaximum(total)
        self.bar.setValue(value)

    def _packagesLoaded(self, id_, packages):
        if self.worker is None or id(self.worker) != id_:
            return

        self.worker = None
        self.bar.setValue(self.bar.maximum())
        self.set_packages(packages)

        self.timer.stop()
        if self.main_widget is not None:
            self.main_widget.show()
            self.loading_widget.hide()


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
