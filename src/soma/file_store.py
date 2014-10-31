from rez.vendor.sh import sh
from soma.exceptions import SomaError
from soma.util import time_as_epoch
from datetime import datetime
from fnmatch import fnmatch
import time
import os.path
import os


class FileStore(object):
    def __init__(self, path, include_patterns=None, ignore_patterns=None):
        """A file store.

        All files written to `path` have their change history stored permanently.
        You can retrieve the contents of a file at a certain point in time. Files
        can also be deleted, and added back later, and this information persists
        as well.

        A file's state is not persisted until either `update` is called for that
        file (even if the file was deleted), or the file is accessed via `read`.

            >>> store = FileStore("./test")
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
            path (str): Path to directory to store files in. Must already exist.
            include_patterns (list of str): Filename patterns to include. If
                None, all files are included by default.
            ignore_patterns (list of str): Filename patterns to ignore.
        """
        if not os.path.isdir(path):
            open(path)  # raises IOError

        self.path = os.path.abspath(path)
        self.include_patterns = include_patterns or []
        self.ignore_patterns = ignore_patterns or []
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

        Args:
            filename (str): Name of file to update. If None, update all files.
        """
        if not self._valid_filename(filename):
            raise SomaError("File in ignore list: %r" % filename)

        proc = self.git.status(filename, short=True, porcelain=True)
        toks = proc.stdout.strip().split()
        if not toks:
            return

        if toks[0] == "??":
            try:
                proc = self.git.add(filename)
            except sh.ErrorReturnCode as e:
                self._error("Error adding file %s to %s" % (filename, self.path), e)

        try:
            proc = self.git.commit(filename, m="", allow_empty_message=True)
        except sh.ErrorReturnCode as e:
            self._error("Error committing file %s to %s" % (filename, self.path), e)

    def read(self, filename, time_=None):
        """Read a file.

        This operation also updates the given file.

        Args:
            time_ (`DateTime` or int): Get the file contents as they were at
                the given time. If int, `time` is interpreted as linux epoch
                time. If None, present time is used.

        Returns:
            None if the file does not/did not exist, or a 3-tuple containing:
            - str: Contents of the file;
            - str: File handle;
            - int: Epoch time of the file commit;
            - str: Author name.
        """
        self.update(filename)

        if time_ is None:
            time_ = int(time.time())

        epoch = time_as_epoch(time_)
        commits = self._file_commits(filename=filename, limit=1, until=epoch)
        if commits:
            commit_hash, commit_time, author = commits[0]
            commit_time = int(commit_time)
        else:
            return None  # file was not committed at or before this time

        try:
            proc = self.git.show("%s:%s" % (commit_hash, filename))
        except sh.ErrorReturnCode:
            return None  # file did not exist at this time

        contents = proc.stdout
        handle = commit_hash
        return contents, handle, commit_time, author

    def file_logs(self, filename, limit=None, since=None, until=None):
        """Get a list of log entries for a file.

        Args:
            filename (str): Name of file.
            limit (int): Maximum number of entries to return.
            since (`DateTime` or int): Only return entries at or after this time.
            until (`DateTime` or int): Only return entries at or before this time.

        Returns:
            List of 3-tuples where each contains:
            - str: File handle;
            - int: Epoch time of the file commit;
            - str: Author name.

            The list is ordered from most recent commit to last.
        """
        return self._file_commits(limit=limit, since=since, until=until,
                                  filename=filename)

    def filenames(self, time_=None):
        """Get the filenames stored at the given time.

        Args:
            time_ (`DateTime` or int): Get the file list as it was at the given
                time. If int, `time` is interpreted as linux epoch time. If None,
                present time is used.

        Returns:
            list of str: List of filenames.
        """
        if time_ is None:  # just a listdir in this case
            return [x for x in os.listdir(self.path)
                    if os.path.isfile(os.path.join(self.path, x))
                    and self._valid_filename(x)]
        else:
            epoch = time_as_epoch(time_)
            commits = self._file_commits(limit=1, until=epoch)
            if commits:
                commit_hash = commits[0][0]
            else:
                return []

            try:
                proc = self.git("ls-tree", commit_hash, name_only=True)
            except sh.ErrorReturnCode as e:
                self._error("Error getting git file listing", e)
            return proc.stdout.strip().split()

    def _valid_filename(self, filename):
        if self.include_patterns and (not any(fnmatch(filename, x)
                                      for x in self.include_patterns)):
            return False

        for pattern in self.ignore_patterns:
            if fnmatch(filename, pattern):
                return False
        return True

    def _file_commits(self, limit=None, since=None, until=None, filename=None):
        # returns [(commit_hash, commit_epoch, author_name)]
        nargs = ["--format=%H %at %an"]
        if limit:
            nargs.append("-n%d" % limit)
        if since is not None:
            nargs.append("--since=%d" % since)
        if until is not None:
            nargs.append("--until=%d" % until)
        if filename:
            nargs.extend(["--", filename])

        try:
            proc = self.git.log(*nargs, _iter=True)
        except sh.ErrorReturnCode as e:
            self._error("Error getting git log", e)

        results = []
        for out in proc:
            out = out.strip()
            if not out:
                continue

            commit_hash, commit_time, author = out.split(None, 2)
            results.append((commit_hash, int(commit_time), author))

        return results

    @classmethod
    def _error(cls, msg, e):
        raise SomaError("%s\n%s" % (msg, str(e)))
