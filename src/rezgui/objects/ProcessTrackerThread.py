from Qt import QtCore
from threading import Lock
import time


class ProcessTrackerThread(QtCore.QThread):

    instanceCountChanged = QtCore.Signal(int, str, int)

    def __init__(self, parent=None):
        super(ProcessTrackerThread, self).__init__(parent)
        self.processes = {}
        self.proc_list = []
        self.pending_procs = []
        self.lock = Lock()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._update)

    def run(self):
        self.timer.start()
        self.exec_()

    def running_instances(self, context, process_name):
        """Get a list of running instances.

        Args:
            context (`ResolvedContext`): Context the process is running in.
            process_name (str): Name of the process.

        Returns:
            List of (`subprocess.Popen`, start-time) 2-tuples, where start_time
            is the epoch time the process was added.
        """
        handle = (id(context), process_name)
        it = self.processes.get(handle, {}).values()
        entries = [x for x in it if x[0].poll() is None]
        return entries

    def add_instance(self, context, process_name, process):
        try:
            self.lock.acquire()
            entry = (id(context), process_name, process, int(time.time()))
            self.pending_procs.append(entry)
        finally:
            self.lock.release()

    def _update(self):
        # add pending instances
        if self.pending_procs:
            try:
                self.lock.acquire()
                pending_procs = self.pending_procs
                self.pending_procs = []
            finally:
                self.lock.release()

            for (context_id, process_name, process, start_time) in pending_procs:
                handle = (context_id, process_name)
                procs = self.processes.get(handle)
                value = (process, start_time)

                if procs is None:
                    self.processes[handle] = {process.pid: value}
                    nprocs = 1
                else:
                    if process.pid not in procs:
                        procs[process.pid] = value
                    nprocs = len(procs)
                self.instanceCountChanged.emit(context_id, process_name, nprocs)

        # rebuild proc list to iterate over
        if self.processes and not self.proc_list:
            for (context_id, process_name), d in self.processes.items():
                for proc, _ in d.values():
                    entry = (context_id, process_name, proc)
                    self.proc_list.append(entry)

        # poll a proc
        if self.proc_list:
            context_id, process_name, proc = self.proc_list.pop()
            if proc.poll() is not None:
                nprocs = self._remove_proc(context_id, process_name, proc.pid)
                self.instanceCountChanged.emit(context_id, process_name, nprocs)

    def _remove_proc(self, context_id, process_name, pid):
        handle = (context_id, process_name)
        procs = self.processes.get(handle)
        if procs is None:
            return 0

        if pid in procs:
            del procs[pid]
        nprocs = len(procs)
        if not procs:
            del self.processes[handle]
        return nprocs


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
