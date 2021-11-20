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
