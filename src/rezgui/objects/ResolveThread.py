from __future__ import print_function

from Qt import QtCore
from rez.exceptions import RezError


class ResolveThread(QtCore.QObject):

    finished = QtCore.Signal()

    def __init__(self, context_model, verbosity=0, max_fails=-1, timestamp=None,
                 show_package_loads=True, buf=None):
        super(ResolveThread, self).__init__()
        self.context_model = context_model
        self.context = None
        self.verbosity = verbosity
        self.max_fails = max_fails
        self.timestamp = timestamp
        self.show_package_loads = show_package_loads
        self.buf = buf
        self.context = None
        self.stopped = False
        self.abort_reason = None
        self.error_message = None

    def run(self):
        package_load_callback = (self._package_load_callback
                                 if self.show_package_loads else None)
        try:
            self.context = self.context_model.resolve_context(
                verbosity=self.verbosity,
                max_fails=self.max_fails,
                timestamp=self.timestamp,
                buf=self.buf,
                callback=self._callback,
                package_load_callback=package_load_callback)
        except RezError as e:
            self.error_message = str(e)

        if not self.stopped:
            self.finished.emit()

    def stop(self):
        self.stopped = True
        self.abort_reason = "Cancelled by user."

    def success(self):
        return bool(self.context and self.context.success)

    def _callback(self, solver_state):
        if self.buf and self.verbosity == 0:
            print("solve step %d..." % solver_state.num_solves, file=self.buf)
        return (not self.stopped), self.abort_reason

    def _package_load_callback(self, package):
        if self.buf:
            print("loading %s..." % str(package), file=self.buf)


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
