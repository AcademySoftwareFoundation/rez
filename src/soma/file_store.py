from rez.vendor.sh import sh
from rez.vendor.enum import Enum
from soma.exceptions import SomaError
from soma.util import time_as_epoch
from datetime import datetime
from fnmatch import fnmatch
import time
import os.path
import os


class FileStatus(Enum):
    """Enum to represent the status of a file in the store."""
    added = ('A',)
    modified = ('M',)
    deleted = ('D',)

    def __init__(self, abbrev):
        self.abbrev = abbrev


class FileStore(object):
    def __init__(self, path, include_patterns=None, ignore_patterns=None,
                 read_only=False):
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

        Note:
            If `read_only` is True, files are never updated. New files or file
            changes that have not been committed will not be visible.

        Note:
            Changes are only stored to one second resolution (a local git repo
            underlies the file store, and it has this limitation). This means
            that if several file updates happen in rapid succession, you may
            only be able to retrieve the state of the latest update in that
            sequence.

        Args:
            path (str): Path to directory to store files in. Must already exist.
            include_patterns (list of str): Filename patterns to include. If
                None, all files are included by default.
            ignore_patterns (list of str): Filename patterns to ignore.
            read_only (bool): If True, files are never updated.
        """
        if not os.path.isdir(path):
            open(path)  # raises IOError

        self.path = os.path.abspath(path)
        self.include_patterns = include_patterns or []
        self.ignore_patterns = ignore_patterns or []
        self.read_only = read_only

        self.git = sh.git.bake(_tty_out=False, _cwd=path)

        if not os.path.exists(os.path.join(self.path, ".git")):
            try:
                self.git.init()
                self.git.commit(message="init", allow_empty=True)
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
        if self.read_only:
            return

        if not self._valid_filename(filename):
            raise SomaError("File in ignore / not in include list: %r" % filename)

        proc = self.git.status(filename, short=True, porcelain=True)
        toks = proc.stdout.strip().split()
        if not toks:
            return

        status = toks[0]
        if status == "??":
            try:
                proc = self.git.add(filename)
            except sh.ErrorReturnCode as e:
                self._error("Error adding file %s to %s" % (filename, self.path), e)

        try:
            proc = self.git.commit(filename, m=status)
        except sh.ErrorReturnCode as e:
            self._error("Error committing file %s to %s" % (filename, self.path), e)

    def read(self, filename, time_=None, blame=False):
        """Read a file.

        This operation also updates the given file.

        Args:
            filename (str): Name of file to read.
            time_ (`DateTime` or int): Get the file contents as they were at
                the given time. If int, `time` is interpreted as linux epoch
                time. If None, present time is used.
            blame (bool): If True, each line of the file's contents will be
                prefixed with git blame information.

        Returns:
            None if the file does not/did not exist, or a 5-tuple containing:
            - str: Contents of the file;
            - str: File handle;
            - int: Epoch time of the file commit;
            - str: Author name;
            - `FileStatus` object.
        """
        self.update(filename)

        if time_ is None:
            time_ = int(time.time())

        epoch = time_as_epoch(time_)
        commits = self._file_commits(filename=filename, limit=1, until=epoch)
        if commits:
            commit_hash, commit_time, author, file_status = commits[0]
        else:
            return None  # file was not committed at or before this time

        handle = commit_hash
        contents = self._file_contents(filename, handle, blame=blame)
        return contents, handle, commit_time, author, file_status

    def read_from_handle(self, filename, handle, blame=False):
        """Read a file given a commit handle.

        Args:
            filename (str): Name of file to read.
            handle (str): Commit handle of file.
            blame (bool): If True, each line of the file's contents will be
                prefixed with git blame information.

        Returns:
            A 4-tuple containing:
            - str: Contents of the file (or None if the file is deleted);
            - int: Epoch time of the file commit;
            - str: Author name;
            - `FileStatus` object.
        """
        try:
            format_arg = "--format=%H %at [%s] %an"
            proc = self.git.log(format_arg, "-n1", handle, "--", filename)
        except sh.ErrorReturnCode as e:
            words = proc.stderr.split()
            if "bad" in words and "object" in words:
                self._error("Invalid file handle:", handle)
            else:
                self._error("Error getting git log", e)

        _, commit_epoch, author_name, file_status = self._parse_log_line(proc.stdout)
        if file_status == FileStatus.deleted:
            contents = None
        else:
            contents = self._file_contents(filename, handle, blame=blame)

        return contents, commit_epoch, author_name, file_status

    def file_logs(self, filename, limit=None, since=None, until=None):
        """Get a list of log entries for a file.

        Args:
            filename (str): Name of file.
            limit (int): Maximum number of entries to return.
            since (`DateTime` or int): Only return entries at or after this time.
            until (`DateTime` or int): Only return entries at or before this time.

        Returns:
            List of 4-tuples where each contains:
            - str: File handle;
            - int: Epoch time of the file commit;
            - str: Author name;
            - `FileStatus` object.

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
        if self.include_patterns and \
                not any(fnmatch(filename, x) for x in self.include_patterns):
            return False
        return not any(fnmatch(filename, x) for x in self.ignore_patterns)

    def _parse_log_line(self, line):
        # returns (commit_hash, commit_epoch, author_name, file_status)
        commit_hash, commit_time, file_status, author = line.split(None, 3)
        file_status = file_status[1:-1]
        if file_status == "??":
            file_status = FileStatus.added
        elif file_status == 'D':
            file_status = FileStatus.deleted
        else:
            file_status = FileStatus.modified
        return commit_hash, int(commit_time), author, file_status

    def _file_commits(self, limit=None, since=None, until=None, filename=None):
        # returns [(commit_hash, commit_epoch, author_name, file_status)]
        nargs = ["--format=%H %at [%s] %an"]
        if limit:
            nargs.append("-n%d" % limit)
        if since is not None:
            nargs.append("--since=%d" % since)
        if until is not None:
            nargs.append("--until=%d" % until)
        if filename:
            nargs.extend(["--", filename])

        # this doesn't run the command until iteration starts
        proc = self.git.log(*nargs, _iter=True)

        def _iter():
            while True:
                try:
                    out = proc.next()
                    yield out
                except sh.ErrorReturnCode as e:
                    words = proc.stderr.split()
                    if "bad" in words and "default" in words and "revision" in words:
                        return  # this is ok, just an empty git repo
                    else:
                        self._error("Error getting git log", e)

        results = []
        for out in _iter():
            out = out.strip()
            if not out:
                continue
            entry = self._parse_log_line(out)
            results.append(entry)

        return results

    def _file_contents(self, filename, handle, blame=False):
        if blame:
            cmd = self.git.blame
            nargs = ["-l", "--root", handle, "--", filename]
        else:
            cmd = self.git.show
            nargs = ["%s:%s" % (handle, filename)]

        try:
            proc = cmd(*nargs)
        except sh.ErrorReturnCode:
            return None  # file did not exist at this time

        return proc.stdout

    def _error(self, msg, e):
        raise SomaError("Error in file store at %r:\n%s\n%s"
                        % (self.path, msg, str(e)))
