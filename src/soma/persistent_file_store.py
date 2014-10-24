from rez.vendor.sh import sh
from soma.exceptions import SomaError
from datetime import datetime
import os.path


class PersistentFileStore(object):
    def __init__(self, path):
        """A persistent file store.

        All files written to `path` have their change history stored permanently.
        You can retrieve the contents of a file at a certain point in time. Files
        can also be deleted, and added back later, and this information persists
        as well.

        A file's state is not persisted until either `update` is called for that
        file (even if the file was deleted), or the file is accessed via `read`.

            >>> store = PersistentFileStore("./test")
            >>> # user creates file foo.txt in test with contents 'hello'
            >>> store.read("foo.txt")
            hello
            >>> t1 = datetime.now()
            >>> # user appends 'world' to foo.txt
            >>> store.read("foo.txt")
            hello world
            >>> store.read("foo.txt", t1)
            hello

        Note that changes are only stored to one second resolution (a local git
        repo underlies the file store, and it has this limitation). This means
        that if several file updates happen in rapid succession, you may only be
        able to retrieve the state of the latest update in that sequence.

        Args:
            path (str): Path to directory to store persistent files in. Must
                already exist.
        """
        if not os.path.isdir(path):
            raise SomaError("Path for persistent file store does not exist: %s" % path)

        self.path = os.path.abspath(path)
        self.git = sh.git.bake(_tty_out=False, _cwd=path)

        if not os.path.exists(os.path.join(self.path, ".git")):
            try:
                proc = self.git.init()
            except sh.ErrorReturnCode as e:
                self._error("Error initialising git repo at %s" % self.path, e)

    def update(self, filename):
        """Update the status of a file in the store.

        Use `update` on a file whenever it changes - to initially add it to
        the store; when its contents change; when it is deleted. An update
        happens automatically when a file is read. If a file is changed
        multiple times before a read, and `update` is not called during that
        time, those intermediate changes will be lost.

        This function has no effect if:
        - the file is already up-to-date in the store;
        - the file does not exist and never did exist.
        """
        filepath = os.path.join(self.path, filename)
        proc = self.git.status(filepath, short=True, porcelain=True)
        toks = proc.stdout.strip().split()
        if toks:
            if toks[0] == "??":
                try:
                    proc = self.git.add(filepath)
                except sh.ErrorReturnCode as e:
                    self._error("Error adding file %s to %s" % (filename, self.path), e)

            try:
                proc = self.git.commit(filepath, m="", allow_empty_message=True)
            except sh.ErrorReturnCode as e:
                self._error("Error committing file %s to %s" % (filename, self.path), e)

    def read(self, filename, time=None):
        """Read a file.

        Args:
            time (`DateTime` or int): Get the file contents as they were at
                the given time. If int, `time` is interpreted as linux epoch
                time. If None, present time is used.

        Returns:
            (str) The contents of the file, or None if the file does not/
                did not exist.
        """
        self.update(filename)
        filepath = os.path.join(self.path, filename)

        if time is None:
            if os.path.isfile(filepath):
                with open(filepath) as f:
                    return f.read()
            else:
                return None

        if isinstance(time, datetime):
            epoch = datetime.utcfromtimestamp(0)
            time = (time - epoch).total_seconds()

        # find most recent commit before or at given time
        try:
            proc = self.git.log("-n1",
                                "--format=%H",
                                "--until=%d" % int(time),
                                filepath)
        except sh.ErrorReturnCode as e:
            print str(e)
            return None

        commit_hash = proc.stdout.strip()
        if not commit_hash:
            return None  # file was not committed at or before this time

        try:
            proc = self.git.show("%s:%s" % (commit_hash, filename))
        except sh.ErrorReturnCode:
            return None  # file did not exist at this time
        return proc.stdout

    @classmethod
    def _error(cls, msg, e):
        raise SomaError("%s\n%s" % (msg, str(e)))
