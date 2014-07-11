from rez.exceptions import ReleaseVCSError
from rez.vendor.version.version import Version
from rez.packages import load_developer_package
from rez.util import which, print_debug
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
            raise ReleaseVCSError("Unknown version control system: %r"
                                  % vcs_name)
        cls = plugin_manager.get_plugin_class('release_vcs', vcs_name)
        return cls(path)

    clss = []
    for vcs_name in vcs_types:
        cls = plugin_manager.get_plugin_class('release_vcs', vcs_name)
        if cls.is_valid_root(path):
            clss.append(cls)
    if len(clss) > 1:
        clss_str = ", ".join(x.name() for x in clss)
        raise ReleaseVCSError("Several version control systems are associated "
                              "with the path %s: %s. Use rez-release --vcs to "
                              "choose." % (path, clss_str))
    elif not clss:
        raise ReleaseVCSError("No version control system for package "
                              "releasing is associated with the path %s"
                              % path)
    else:
        return clss[0](path)


class ReleaseVCS(object):
    """A version control system (VCS) used to release Rez packages.
    """
    def __init__(self, path):
        assert(self.is_valid_root(path))
        self.path = path
        self.package = load_developer_package(path)
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
        attrs = dict((k, str(v)) for k, v in self.package.metadata.iteritems()
                     if isinstance(v, (basestring, Version)))

        tag_name = self.type_settings.tag_name.format(**attrs)
        if not tag_name:
            tag_name = "unversioned"

        if message is None:
            message = "Rez created release tag: %s" % tag_name

        self._create_tag_impl(tag_name, message)

    def _create_tag_impl(self, tag_name, message=None):
        """Only implement this if you are using the default implementation of
        create_release_tag()."""
        raise NotImplementedError

    def _cmd(self, *nargs):
        """Convenience function for executing a program such as 'git' etc."""
        cmd_str = ' '.join(nargs)
        if self.package.config.debug("package_release"):
            print_debug("Running command: %s" % cmd_str)

        p = subprocess.Popen(nargs, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=self.path)
        out, err = p.communicate()
        if p.returncode:
            raise ReleaseVCSError("command failed: %s\n%s" % (cmd_str, err))
        out = out.strip()
        if out:
            return [x.rstrip() for x in out.split('\n')]
        else:
            return []
