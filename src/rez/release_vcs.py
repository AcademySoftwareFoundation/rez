from rez.exceptions import ReleaseVCSError
from rez.packages import get_developer_package
from rez.util import which
from rez.utils.execution import Popen
from rez.utils.logging_ import print_debug
from rez.utils.filesystem import walk_up_dirs
from pipes import quote
import subprocess


def get_release_vcs_types():
    """Returns the available VCS implementations - git, hg etc."""
    from rez.plugin_managers import plugin_manager
    return plugin_manager.get_plugins('release_vcs')


def create_release_vcs(path, vcs_name=None):
    """Return a new release VCS that can release from this source path."""
    from rez.plugin_managers import plugin_manager
    vcs_types = get_release_vcs_types()
    if vcs_name:
        if vcs_name not in vcs_types:
            raise ReleaseVCSError("Unknown version control system: %r" % vcs_name)
        cls = plugin_manager.get_plugin_class('release_vcs', vcs_name)
        return cls(path)

    classes_by_level = {}
    for vcs_name in vcs_types:
        cls = plugin_manager.get_plugin_class('release_vcs', vcs_name)
        result = cls.find_vcs_root(path)
        if not result:
            continue
        vcs_path, levels_up = result
        classes_by_level.setdefault(levels_up, []).append((cls, vcs_path))

    if not classes_by_level:
        raise ReleaseVCSError(
            "No version control system for package "
            "releasing is associated with the path %s" % path
        )

    # it's ok to have multiple results, as long as there is only one at the
    # "closest" directory up from this dir - ie, if we start at:
    #    /blah/foo/pkg_root
    # and these dirs exist:
    #    /blah/.hg
    #    /blah/foo/.git
    # ...then this is ok, because /blah/foo/.git is "closer" to the original
    # dir, and will be picked. However, if these two directories exist:
    #    /blah/foo/.git
    #    /blah/foo/.hg
    # ...then we error, because we can't decide which to use

    lowest_level = sorted(classes_by_level)[0]
    clss = classes_by_level[lowest_level]
    if len(clss) > 1:
        clss_str = ", ".join(x[0].name() for x in clss)
        raise ReleaseVCSError("Several version control systems are associated "
                              "with the path %s: %s. Use rez-release --vcs to "
                              "choose." % (path, clss_str))
    else:
        cls, vcs_root = clss[0]
        return cls(pkg_root=path, vcs_root=vcs_root)


class ReleaseVCS(object):
    """A version control system (VCS) used to release Rez packages.
    """
    def __init__(self, pkg_root, vcs_root=None):
        if vcs_root is None:
            result = self.find_vcs_root(pkg_root)
            if not result:
                raise ReleaseVCSError("Could not find %s repository for the "
                                      "path %s" % (self.name(), pkg_root))
            vcs_root = result[0]
        else:
            assert(self.is_valid_root(vcs_root))

        self.vcs_root = vcs_root
        self.pkg_root = pkg_root
        self.package = get_developer_package(pkg_root)
        self.type_settings = self.package.config.plugins.release_vcs
        self.settings = self.type_settings.get(self.name())

    @classmethod
    def name(cls):
        """Return the name of the VCS type, eg 'git'."""
        raise NotImplementedError

    @classmethod
    def find_executable(cls, name):
        exe = which(name)
        if not exe:
            raise ReleaseVCSError("Couldn't find executable '%s' for VCS '%s'"
                                  % (name, cls.name()))
        return exe

    @classmethod
    def is_valid_root(cls, path):
        """Return True if the given path is a valid root directory for this
        version control system.

        Note that this is different than whether the path is under the
        control of this type of vcs; to answer that question,
        use find_vcs_root
        """
        raise NotImplementedError

    @classmethod
    def search_parents_for_root(cls):
        """Return True if this vcs type should check parent directories to
        find the root directory
        """
        raise NotImplementedError

    @classmethod
    def find_vcs_root(cls, path):
        """Try to find a version control root directory of this type for the
        given path.

        If successful, returns (vcs_root, levels_up), where vcs_root is the
        path to the version control root directory it found, and levels_up is an
        integer indicating how many parent directories it had to search through
        to find it, where 0 means it was found in the indicated path, 1 means it
        was found in that path's parent, etc. If not sucessful, returns None
        """
        if cls.search_parents_for_root():
            valid_dirs = walk_up_dirs(path)
        else:
            valid_dirs = [path]
        for i, current_path in enumerate(valid_dirs):
            if cls.is_valid_root(current_path):
                return current_path, i
        return None

    def validate_repostate(self):
        """Ensure that the VCS working copy is up-to-date."""
        raise NotImplementedError

    def get_current_revision(self):
        """Get the current revision, this can be any type (str, dict etc)
        appropriate to your VCS implementation.

        Note:
            You must ensure that a revision contains enough information to
            clone/export/checkout the repo elsewhere - otherwise you will not
            be able to implement `export`.
        """
        raise NotImplementedError

    def get_changelog(self, previous_revision=None, max_revisions=None):
        """Get the changelog text since the given revision.

        If previous_revision is not an ancestor (for example, the last release
        was from a different branch) you should still return a meaningful
        changelog - perhaps include a warning, and give changelog back to the
        last common ancestor.

        Args:
            previous_revision: The revision to give the changelog since. If
            None, give the entire changelog.

        Returns:
            Changelog, as a string.
        """
        raise NotImplementedError

    def tag_exists(self, tag_name):
        """Test if a tag exists in the repo.

        Args:
            tag_name (str): Tag name to check for.

        Returns:
            bool: True if the tag exists, False otherwise.
        """
        raise NotImplementedError

    def create_release_tag(self, tag_name, message=None):
        """Create a tag in the repo.

        Create a tag in the repository representing the release of the
        given version.

        Args:
            tag_name (str): Tag name to write to the repo.
            message (str): Message string to associate with the release.
        """
        raise NotImplementedError

    @classmethod
    def export(cls, revision, path):
        """Export the repository to the given path at the given revision.

        Note:
            The directory at `path` must not exist, but the parent directory
            must exist.

        Args:
            revision (object): Revision to export; current revision if None.
            path (str): Directory to export the repository to.
        """
        raise NotImplementedError

    def _cmd(self, *nargs):
        """Convenience function for executing a program such as 'git' etc."""
        cmd_str = ' '.join(map(quote, nargs))

        if self.package.config.debug("package_release"):
            print_debug("Running command: %s" % cmd_str)

        p = Popen(nargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                  cwd=self.pkg_root, text=True)
        out, err = p.communicate()

        if p.returncode:
            print_debug("command stdout:")
            print_debug(out)
            print_debug("command stderr:")
            print_debug(err)
            raise ReleaseVCSError("command failed: %s\n%s" % (cmd_str, err))
        out = out.strip()
        if out:
            return [x.rstrip() for x in out.split('\n')]
        else:
            return []


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
