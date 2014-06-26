from rez.release_vcs import ReleaseVCS
from rez.config import config
from rez.exceptions import ReleaseVCSUnsupportedError, ReleaseVCSError
import functools
import os.path
import re
import sys


class GitReleaseVCS(ReleaseVCS):
    @classmethod
    def name(cls):
        return 'git'

    def __init__(self, path):
        super(GitReleaseVCS, self).__init__(path)
        self.executable = self.find_executable('git')

        try:
            self.git("rev-parse")
        except ReleaseVCSError:
            raise ReleaseVCSUnsupportedError("%s is not a git repository" % path)

    @classmethod
    def is_valid_root(cls, path):
        return os.path.isdir(os.path.join(path, '.git'))

    def git(self, *nargs):
        return self._cmd(self.executable, *nargs)

    def get_relative_to_remote(self):
        """Return the number of commits we are relative to the remote. Negative
        is behind, positive in front, zero means we are matched to remote.
        """
        s = self.git("status", "--short", "-b")[0]
        r = re.compile("\[([^\]]+)\]")
        toks = r.findall(s)
        if toks:
            try:
                s2 = toks[-1]
                adj,n = s2.split()
                assert(adj in ("ahead", "behind"))
                n = int(n)
                return -n if adj == "behind" else n
            except Exception as e:
                raise ReleaseVCSError(
                    ("Problem parsing first line of result of 'git status "
                     "--short -b' (%s):\n%s") % (s, str(e)))
        else:
            return 0

    def get_tracking_branch(self):
        """Returns (remote, branch) tuple, or None,None if there is no remote."""
        try:
            remote_uri = self.git("rev-parse", "--abbrev-ref",
                                  "--symbolic-full-name", "@{u}")[0]
            return remote_uri.split('/', 1)
        except Exception as e:
            if "No upstream branch" not in str(e):
                raise e
        return (None,None)

    def validate_repostate(self):
        b = self.git("rev-parse", "--is-bare-repository")
        if b == "true":
            raise ReleaseVCSError("Could not release: bare git repository")

        # check for uncommitted changes
        try:
            self.git("diff-index", "--quiet", "HEAD")
        except ReleaseVCSError:
            msg = "Could not release: there are uncommitted changes:\n"
            statmsg = self.git("diff-index", "--stat", "HEAD")
            msg += '\n'.join(statmsg)
            raise ReleaseVCSError(msg)

        # check if we are behind/ahead of remote
        remote,remote_branch = self.get_tracking_branch()
        if remote:
            self.git("remote", "update")
            n = self.get_relative_to_remote()
            if n:
                s = "ahead of" if n>0 else "behind"
                remote_uri = '/'.join((remote, remote_branch))
                raise ReleaseVCSError(("Could not release: %d commits " + \
                    "%s %s.") % (abs(n), s, remote_uri))

    def get_changelog(self, previous_revision=None):
        prev_commit = (previous_revision or {}).get("commit")
        if prev_commit:
            # git returns logs to last common ancestor, so even if previous
            # release was from a different branch, this is ok
            commit_range = "%s..HEAD" % prev_commit
            return self.git("log", commit_range)
        else:
            return self.git("log")

    def get_current_revision(self):
        doc = dict(commit=self.git("rev-parse", "HEAD")[0])

        def _branch():
            return self.git("rev-parse", "--abbrev-ref", "HEAD")[0]

        def _tracking_branch():
            return self.git("rev-parse", "--abbrev-ref",
                            "--symbolic-full-name", "@{u}")[0]

        def _url(op):
            origin = doc["tracking_branch"].split('/')[0]
            lines = self.git("remote", "-v")
            lines = [x for x in lines if origin in x.split()]
            lines = [x for x in lines if ("(%s)" % op) in x.split()]
            try:
                return lines[0].split()[1]
            except:
                raise ReleaseVCSError("failed to parse %s url from:\n%s"
                                      % (op, '\n'.join(lines)))

        def _get(key, fn):
            try:
                doc[key] = fn()
            except Exception as e:
                if config.debug("package_release"):
                    print >> sys.stderr, "WARNING: Error retrieving %s: %s" \
                        % (key, str(e))

        _get("branch", _branch)
        _get("tracking_branch", _tracking_branch)
        _get("fetch_url", functools.partial(_url, "fetch"))
        _get("push_url", functools.partial(_url, "push"))
        return doc

    def _create_tag_impl(self, tag_name, message=None):
        # check if tag already exists
        if self.git("tag", tag_name):
            print "Skipped tag creation, tag '%s' already exists" % tag_name
            return

        # create tag
        print "Creating tag '%s'..." % tag_name
        args = ["tag", "-a", tag_name]
        if message:
            args += ["-m", message]
        self.git(*args)

        # push tag
        remote, remote_branch = self.get_tracking_branch()
        if remote is None:
            return

        remote_uri = '/'.join((remote, remote_branch))
        print "Pushing tag '%s' to %s..." % (tag_name, remote_uri)
        self.git("push", remote, tag_name)


def register_plugin():
    return GitReleaseVCS
