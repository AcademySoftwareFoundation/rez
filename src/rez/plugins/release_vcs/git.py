from rez.release_vcs import ReleaseVCS
from rez.exceptions import ReleaseVCSUnsupportedError, ReleaseVCSError
from rez import plugin_factory
import subprocess
import os.path
import re
import sys

# TODO port fully to git cli. GitPython contains bugs, and help on cli much
# easier to find, so maintenance will be easier.
import git


class GitReleaseVCS(ReleaseVCS):
    executable = ReleaseVCS.find_executable('git')

    @classmethod
    def name(cls):
        return 'git'

    def __init__(self, path):
        super(GitReleaseVCS, self).__init__(path)

        try:
            self.repo = git.Repo(path, odbt=git.GitCmdObjectDB)
        except git.exc.InvalidGitRepositoryError:
            raise ReleaseVCSUnsupportedError("%s is not a git repository" % path)

    @classmethod
    def is_valid_root(cls, path):
        return os.path.isdir(os.path.join(path, '.git'))

    def git(self, *nargs):
        cmd = [self.executable] + list(nargs)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             cwd=self.path)
        out,err = p.communicate()
        if p.returncode:
            raise ReleaseVCSError("command failed: %s\n%s" % (' '.join(cmd), err))
        return [x.strip() for x in out.split('\n')]

    def validate_repostate(self):
        if self.repo.bare:
            raise ReleaseVCSError("'%s' is a bare git repository" % self.path)

        untrackedFiles = self.repo.untracked_files
        if untrackedFiles:
            print >> sys.stderr, "The following files are untracked:\n"
            for file in untrackedFiles:
                print >> sys.stderr, file
                raise ReleaseVCSError("There are untracked files.")

        workingCopyDiff = self.repo.index.diff(None)
        if workingCopyDiff:
            print >> sys.stderr, "The following files are modified:\n"
            for diff in workingCopyDiff:
                print >> sys.stderr, diff.a_blob.path
                raise ReleaseVCSError("There are modified files.")

        if self.repo.is_dirty() or self.git_ahead_of_remote(self.repo):
            raise ReleaseVCSError(("'%s' is not in a state to release - you may " + \
                "need to git commit and/or git push and/or git pull:\n%s") \
                % (self.path, self.repo.git.status()))

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
        print "Create tag '%s'..." % tag_name
        remote = self.repo.remote()
        self.repo.create_tag(tag_name, a=True, m=message)

        print "Pushing tag '%s' to %s..." % (tag_name, remote.url)
        push_result = remote.push(tags=True)
        if not push_result:
            print("failed to push the new tag to the remote, you have to run "
                  "'git push --tags' manually.")

    def git_ahead_of_remote(self, repo):
        """
        Checks that the git repo (git.Repo instance) is
        not ahead of its configured remote. Specifically we
        check that the message that git status returns does not
        contain "# Your branch is ahead of '[a-zA-Z/]+' by \d+ commit"
        """
        status_message = self.repo.git.status()
        return re.search(r"# Your branch is ahead of '.+' by \d+ commit",
                         status_message) != None



class GitReleaseVCSFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return GitReleaseVCS
