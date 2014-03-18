from rez.release_vcs import ReleaseVCS
from rez.exceptions import ReleaseVCSUnsupportedError, ReleaseVCSError
from rez import plugin_factory
import os.path
import re
import git



class GitReleaseVCS(ReleaseVCS):
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

    def get_changelog(self):
        return "TODO"

    def get_current_revision(self):
        # TODO
        return {}

    def _create_tag_impl(self, tag_name, message=None):
        remote = self.repo.remote()
        print("rez-release: creating project tag: '%s' and pushing to: %s" \
            % (tag_name, remote.url))

        self.repo.create_tag(tag_name, a=True, m=message)

        push_result = remote.push()
        if not push_result:
            print("failed to push to remote, you have to run 'git push' manually.")

        push_result = remote.push(tags=True)
        if not push_result:
            print("failed to push the new tag to the remote, you have to run "
                  "'git push --tags' manually.")

    def export_source(self, dest_path):
        try:
            self.repo.git.checkout_index(a=True, prefix=dest_path)
            self.git_checkout_index_submodules(self.repo.submodules, dest_path)
        except Exception, e:
            raise ReleaseVCSError("git checkout-index failed: %s" % str(e))

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

    def git_checkout_index_submodules(self, submodules, subdir):
        """
        Recursively runs checkout-index on each submodule and its submodules and
        so forth, duplicating the submodule directory tree in subdir
        submodules - Iterable list of submodules
        subdir - The target base directory that should contain each
                    of the checkout-indexed submodules
        """
        for submodule in submodules:
            submodule_subdir = os.path.join(subdir, submodule.path) + os.sep
            if not os.path.exists(submodule_subdir):
                os.mkdir(submodule_subdir)
            submodule_repo = git.Repo(submodule.abspath)
            print(("rez-release: git-exporting (checkout-index) clean copy of "
                  "(submodule: %s) to %s...") % (submodule.path, submodule_subdir))
            submodule_repo.git.checkout_index(a=True, prefix=submodule_subdir)
            self.git_checkout_index_submodules(submodule_repo.submodules, submodule_subdir)



class GitReleaseVCSFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return GitReleaseVCS
