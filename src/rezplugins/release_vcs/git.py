"""
Git version control
"""
from __future__ import print_function
from rez.release_vcs import ReleaseVCS
from rez.utils.logging_ import print_error, print_warning, print_debug
from rez.exceptions import ReleaseVCSError
from shutil import rmtree
import functools
import os.path
import re


class GitReleaseVCSError(ReleaseVCSError):
    pass


class GitReleaseVCS(ReleaseVCS):

    schema_dict = {
        "allow_no_upstream": bool}

    @classmethod
    def name(cls):
        return 'git'

    def __init__(self, pkg_root, vcs_root=None):
        super(GitReleaseVCS, self).__init__(pkg_root, vcs_root=vcs_root)
        self.executable = self.find_executable('git')

        try:
            self.git("rev-parse")
        except ReleaseVCSError:
            raise GitReleaseVCSError("%s is not a git repository" %
                                     self.vcs_root)

    @classmethod
    def is_valid_root(cls, path):
        return os.path.isdir(os.path.join(path, '.git'))

    @classmethod
    def search_parents_for_root(cls):
        return True

    def git(self, *nargs):
        return self._cmd(self.executable, *nargs)

    def get_relative_to_remote(self):
        """Return the number of commits we are relative to the remote. Negative
        is behind, positive in front, zero means we are matched to remote.  if
        we are both behind and ahead then only the ahead value will be reported.
        """
        s = self.git("status", "--short", "-b")[0]
        r = re.compile("\[([^\]]+)\]")
        toks = r.findall(s)
        if toks:
            try:
                s2 = toks[-1]
                adj, n = s2.split(",")[0].split()
                assert(adj in ("ahead", "behind"))
                n = int(n)
                return -n if adj == "behind" else n
            except Exception as e:
                raise ReleaseVCSError(
                    ("Problem parsing first line of result of 'git status "
                     "--short -b' (%s):\n%s") % (s, str(e)))
        else:
            return 0

    def get_local_branch(self):
        """Returns the label of the current local branch."""
        return self.git("rev-parse", "--abbrev-ref", "HEAD")[0]

    def get_tracking_branch(self):
        """Returns (remote, branch) tuple, or (None, None) if there is no
        remote.
        """
        try:
            remote_uri = self.git("rev-parse", "--abbrev-ref",
                                  "--symbolic-full-name", "@{u}")[0]
            return remote_uri.split('/', 1)
        except Exception as e:
            # capitalization of message changed sometime between git 1.8.3
            # and 2.12 - used to be "No upstream", now "no upstream"..
            errmsg = str(e).lower()
            if ("no upstream branch" not in errmsg
                    and "no upstream configured" not in errmsg):
                raise e
        return (None, None)

    def validate_repostate(self):
        b = self.git("rev-parse", "--is-bare-repository")
        if b == "true":
            raise ReleaseVCSError("Could not release: bare git repository")

        remote, remote_branch = self.get_tracking_branch()

        # check for upstream branch
        if remote is None and (not self.settings.allow_no_upstream):
            raise ReleaseVCSError(
                "Release cancelled: there is no upstream branch (git cannot see "
                "a remote repo - you should probably FIX THIS FIRST!). To allow "
                "the release, set the config entry "
                "'plugins.release_vcs.git.allow_no_upstream' to true.")

        # check we are releasing from a valid branch
        releasable_branches = self.type_settings.releasable_branches
        if releasable_branches:
            releasable = False
            current_branch_name = self.get_local_branch()
            for releasable_branch in releasable_branches:
                if re.search(releasable_branch, current_branch_name):
                    releasable = True
                    break

            if not releasable:
                raise ReleaseVCSError(
                    "Could not release: current branch is %s, must match "
                    "one of: %s"
                    % (current_branch_name, ', '.join(releasable_branches)))

        # check for untracked files
        output = self.git("ls-files", "--other", "--exclude-standard")
        if output:
            msg = "Could not release: there are untracked files:\n"
            msg += '\n'.join(output)
            raise ReleaseVCSError(msg)

        # check for uncommitted changes
        try:
            self.git("diff-index", "--quiet", "HEAD")
        except ReleaseVCSError:
            msg = "Could not release: there are uncommitted changes:\n"
            statmsg = self.git("diff-index", "--stat", "HEAD")
            msg += '\n'.join(statmsg)
            raise ReleaseVCSError(msg)

        # check if we are behind/ahead of remote
        if remote:
            self.git("remote", "update", remote)
            n = self.get_relative_to_remote()
            if n:
                s = "ahead of" if n > 0 else "behind"
                remote_uri = '/'.join((remote, remote_branch))
                raise ReleaseVCSError(
                    "Could not release: %d commits %s %s."
                    % (abs(n), s, remote_uri))

    def get_changelog(self, previous_revision=None, max_revisions=None):
        prev_commit = None
        if previous_revision is not None:
            try:
                prev_commit = previous_revision["commit"]
            except:
                if self.package.config.debug("package_release"):
                    print_debug("couldn't determine previous commit from: %r"
                                % previous_revision)

        args = ["log"]
        if max_revisions:
            args.extend(["-n", str(max_revisions)])
        if prev_commit:
            # git returns logs to last common ancestor, so even if previous
            # release was from a different branch, this is ok
            try:
                commit_range = "%s..HEAD" % prev_commit
                stdout = self.git("log", commit_range)
            except ReleaseVCSError:
                # Special case where the sha stored in the latest version does not exists due to the
                # git ->github migration where we rewrote the history of the repos
                stdout = self.git("log")
        else:
            stdout = self.git("log")
        return '\n'.join(stdout)

    def get_current_revision(self):
        doc = dict(commit=self.git("rev-parse", "HEAD")[0])

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
                value = fn()
                doc[key] = value
                return (value is not None)
            except Exception as e:
                print_error("Error retrieving %s: %s" % (key, str(e)))
                return False

        def _tracking_branch():
            remote, remote_branch = self.get_tracking_branch()
            if remote is None:
                return None
            else:
                return "%s/%s" % (remote, remote_branch)

        _get("branch", self.get_local_branch)
        if _get("tracking_branch", _tracking_branch):
            _get("fetch_url", functools.partial(_url, "fetch"))
            _get("push_url", functools.partial(_url, "push"))
        return doc

    def tag_exists(self, tag_name):
        tags = self.git("tag")
        return (tag_name in tags)

    def create_release_tag(self, tag_name, message=None):
        if self.tag_exists(tag_name):
            return

        # create tag
        print("Creating tag '%s'..." % tag_name)
        args = ["tag", "-a", tag_name]
        args += ["-m", message or '']
        self.git(*args)

        # push tag
        remote, remote_branch = self.get_tracking_branch()
        if remote is None:
            return

        remote_uri = '/'.join((remote, remote_branch))
        print("Pushing tag '%s' to %s..." % (tag_name, remote_uri))
        self.git("push", remote, tag_name)

    @classmethod
    def export(cls, revision, path):
        cwd = os.getcwd()
        url = revision["fetch_url"]
        commit = revision["commit"]
        path_, dirname = os.path.split(path)
        gitdir = os.path.join(path, ".git")

        with retain_cwd():
            os.chdir(path_)
            git.clone(url, dirname)
            os.chdir(path)
            git.checkout(commit)
            rmtree(gitdir)


def register_plugin():
    return GitReleaseVCS


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
