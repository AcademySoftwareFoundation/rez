from Qt import QtCore
from rez.packages import iter_packages


class LoadPackagesThread(QtCore.QObject):
    """Load packages in a separate thread.

    Packages are loaded in decreasing version order.
    """
    progress = QtCore.Signal(int, int)
    finished = QtCore.Signal(object)

    def __init__(self, package_paths, package_name, range_=None,
                 package_attributes=None, callback=None):
        super(LoadPackagesThread, self).__init__()
        self.stopped = False
        self.package_paths = package_paths
        self.package_name = package_name
        self.range_ = range_
        self.package_attributes = package_attributes
        self.callback = callback

    def stop(self):
        self.stopped = True

    def run(self):
        it = iter_packages(name=self.package_name, paths=self.package_paths, range_=self.range_)
        packages = sorted(it, key=lambda x: x.version, reverse=True)
        num_packages = len(packages)
        self.progress.emit(0, num_packages)

        for i, package in enumerate(packages):
            if self.stopped:
                return
            if self.callback and not self.callback(package):
                break

            for attr in self.package_attributes:
                getattr(package, attr)  # cause load and/or data validation
            self.progress.emit(i + 1, num_packages)

        if not self.stopped:
            self.finished.emit(packages)


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
