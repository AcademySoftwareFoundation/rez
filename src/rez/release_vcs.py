from rez.exceptions import ReleaseVCSUnsupportedError, ReleaseVCSError
from rez.resources import load_package_metadata, load_package_settings
from rez.util import which
import subprocess



def get_release_vcs_types():
    """Returns the available VCS implementations - git, hg etc."""
    from rez.plugin_managers import release_vcs_plugin_manager
    return release_vcs_plugin_manager().get_plugins()


def create_release_vcs(path):
    """Return a new release VCS that can release from this source path."""
    from rez.plugin_managers import release_vcs_plugin_manager
    for vcs_name in get_release_vcs_types():
        cls = release_vcs_plugin_manager().get_plugin_class(vcs_name)
        if cls.is_valid_root(path):
            return cls(path)

    raise ReleaseVCSError("No version control system for package releasing is "
                          "associated with the path %s" % path)



class ReleaseVCS(object):
    """A version control system (VCS) used to release Rez packages.
    """
    def __init__(self, path):
        assert(self.is_valid_root(path))
        self.path = path
        self.metadata,_ = load_package_metadata(path)
        self.settings = load_package_settings(self.metadata)

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
        """Return True if this release mode works with the given root path."""
        raise NotImplementedError

    def validate_repostate(self):
        """Ensure that the VCS working copy is up-to-date."""
        raise NotImplementedError

    def get_current_revision(self):
        """Get the current revision, this can be any type (str, dict etc)
        appropriate to your VCS implementation.
        """
        raise NotImplementedError

    def get_changelog(self, previous_revision=None):
        """Get the changelog text since the given revision.

        If previous_revision is not an ancestor (for example, the last release
        was from a different branch) you should still return a meaningful
        changelog - perhaps include a warning, and give changelog back to the
        last common ancestor.

        Args:
            previous_revision: The revision to give the changelog since. If
            None, give the entire changelog.

        Returns:
            Changelog, as a list of strings.
        """
        raise NotImplementedError

    def create_release_tag(self, message=None):
        """Create a tag in the repo.

        Create a tag in the repository representing the release of the
        given version.

        Args:
            message: Message string to associate with the release.
        """
        attrs = dict((k,v) for k,v in self.metadata.iteritems() \
            if isinstance(v, basestring))

        tag_name = self.settings.vcs_tag_name.format(**attrs)
        if not tag_name:
            tag_name = "unversioned"

        if message is None:
            message = "Rez created release tag: %s" % tag_name

        return self._create_tag_impl(tag_name, message)

    def _create_tag_impl(self, tag_name, message=None):
        """Only implement this if you are using the default implementation of
        create_release_tag()
        """
        raise NotImplementedError

    def _cmd(self, *nargs):
        """Convenience function for executing a program such as 'git' etc."""
        cmd_str = ' '.join(nargs)
        if self.settings.debug_package_release:
            print "Running command: %s" % cmd_str

        p = subprocess.Popen(nargs, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=self.path)
        out,err = p.communicate()
        if p.returncode:
            raise ReleaseVCSError("command failed: %s\n%s" % (cmd_str, err))
        return [x.rstrip() for x in out.strip().split('\n')]
