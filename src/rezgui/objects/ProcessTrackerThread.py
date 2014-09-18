from rezgui.qt import QtCore, QtGui
from threading import Lock


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

    def num_instances(self, context, process_name):
        handle = (id(context), process_name)
        procs = self.processes.get(handle, {})
        return len(procs)

    def add_instance(self, context, process_name, process):
        try:
            self.lock.acquire()
            self.pending_procs.append((id(context), process_name, process))
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

            for (context_id, process_name, process) in pending_procs:
                handle = (context_id, process_name)
                procs = self.processes.get(handle)
                if procs is None:
                    self.processes[handle] = {process.pid: process}
                    nprocs = 1
                else:
                    if process.pid not in procs:
                        procs[process.pid] = process
                    nprocs = len(procs)
                self.instanceCountChanged.emit(context_id, process_name, nprocs)

        # rebuild proc list to iterate over
        if self.processes and not self.proc_list:
            for (context_id, process_name), d in self.processes.iteritems():
                for proc in d.itervalues():
                    self.proc_list.append((context_id, process_name, proc))

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
