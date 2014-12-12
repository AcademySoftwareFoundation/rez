from rez.utils.logging_ import print_warning
from rez.packages import load_developer_package


def get_release_hook_types():
    """Returns the available release hook implementations."""
    from rez.plugin_managers import plugin_manager
    return plugin_manager.get_plugins('release_hook')


def create_release_hook(name, source_path):
    """Return a new release hook of the given type."""
    from rez.plugin_managers import plugin_manager
    return plugin_manager.create_instance('release_hook',
                                          name,
                                          source_path=source_path)


def create_release_hooks(names, source_path):
    hooks = []
    for name in names:
        try:
            hook = create_release_hook(name, source_path)
            hooks.append(hook)
        except:
            print_warning("Release hook '%s' is not available." % name)
    return hooks


class ReleaseHook(object):
    """An object that allows for custom behaviour during releases.

    A release hook provides methods that you implement to inject custom
    behaviour during parts of the release process. For example, the builtin
    'email' hook sends a post-release email to a configured address.
    """
    @classmethod
    def name(cls):
        """ Return name of source retriever, eg 'git'"""
        raise NotImplementedError

    def __init__(self, source_path):
        """Create a release hook.

        Args:
            source_path: Path containing source that was released.
        """
        self.source_path = source_path
        self.package = load_developer_package(source_path)
        self.type_settings = self.package.config.plugins.release_hook
        self.settings = self.type_settings.get(self.name())

    def pre_build(self, user, install_path, release_message=None,
                  changelog=None, previous_version=None,
                  previous_revision=None):
        """Pre-build hook.

        Args:
            user: Name of person who did the release.
            install_path: Directory the package was installed into.
            release_message: User-supplied release message.
            changelog: List of strings describing changes since last release.
            previous_version: Version object - previously-release package, or
                None if no previous release.
            previous_revision: Revision of previously-releaved package (type
                depends on repo - see ReleaseVCS.get_current_revision().

        Note:
            This method should raise a `ReleaseError` if the release process
            should be cancelled.
        """
        pass

    def pre_release(self, user, install_path, release_message=None,
                    changelog=None, previous_version=None,
                    previous_revision=None):
        """Pre-release hook.

        Args:
            user: Name of person who did the release.
            install_path: Directory the package was installed into.
            release_message: User-supplied release message.
            changelog: List of strings describing changes since last release.
            previous_version: Version object - previously-release package, or
                None if no previous release.
            previous_revision: Revision of previously-releaved package (type
                depends on repo - see ReleaseVCS.get_current_revision().

        Note:
            This method should raise a `ReleaseError` if the release process
            should be cancelled.
        """
        pass

    def post_release(self, user, install_path, release_message=None,
                     changelog=None, previous_version=None,
                     previous_revision=None):
        """Post-release hook.

        Args:
            user: Name of person who did the release.
            install_path: Directory the package was installed into.
            release_message: User-supplied release message.
            changelog: List of strings describing changes since last release.
            previous_version: Version of previously-release package, None if
                no previous release.
            previous_revision: Revision of previously-releaved package (type
                depends on repo - see ReleaseVCS.get_current_revision().
        """
        pass
