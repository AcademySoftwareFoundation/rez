from rez.release_vcs import ReleaseVCS
from rez.exceptions import ReleaseVCSUnsupportedError, ReleaseVCSError
from rez import plugin_factory
import os.path
import re
import sys



class GitReleaseVCS(ReleaseVCS):
    executable = ReleaseVCS.find_executable('git')

    @classmethod
    def name(cls):
        return 'git'

    def __init__(self, path):
        super(GitReleaseVCS, self).__init__(path)

        try:
            #self.repo = git.Repo(path, odbt=git.GitCmdObjectDB)
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
            except e:
                raise ReleaseVCSError( \
                    ("Problem parsing first line of result of 'git status " + \
                    "--short -b' (%s):\n%s") % (s, str(e)))
        else:
            return 0

    def get_tracking_branch(self):
        """Returns (remote, branch) tuple, or None,None if there is no remote."""
        try:
            remote_uri = self.git("rev-parse", "--abbrev-ref",
                                  "--symbolic-full-name", "@{u}")[0]
            return remote_uri.split('/', 1)
        except e:
            if "No upstream" not in str(e):
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
        commit = self.git("rev-parse", "HEAD")[0]
        branch = self.git("rev-parse", "--abbrev-ref", "HEAD")[0]
        return dict(commit=commit,
                    branch=branch)

    def _create_tag_impl(self, tag_name, message=None):
        # create tag
        print "Creating tag '%s'..." % tag_name
        args = ["tag", "-a", tag_name]
        if message:
            args += ["-m", message]
        self.git(*args)

        # push tag
        remote,remote_branch = self.get_tracking_branch()
        if remote is None:
            return

        remote_uri = '/'.join((remote, remote_branch))
        print "Pushing tag '%s' to %s..." % (tag_name, remote_uri)
        self.git("push", remote, tag_name)



class GitReleaseVCSFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return GitReleaseVCS
