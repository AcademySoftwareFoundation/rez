from rez.utils.logging_ import print_warning, print_debug
from rez.packages_ import get_developer_package
from rez.vendor.enum import Enum


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
        except Exception:
            import traceback
            print_warning("Release hook '%s' is not available." % name)
            print_debug(traceback.format_exc())
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
        self.package = get_developer_package(source_path)
        self.type_settings = self.package.config.plugins.release_hook
        self.settings = self.type_settings.get(self.name())

    def pre_build(self, user, install_path, variants=None, release_message=None,
                  changelog=None, previous_version=None,
                  previous_revision=None, **kwargs):
        """Pre-build hook.

        Args:
            user: Name of person who did the release.
            install_path: Directory the package was installed into.
            variants: List of variant indices we are attempting to build, or
                None
            release_message: User-supplied release message.
            changelog: List of strings describing changes since last release.
            previous_version: Version object - previously-release package, or
                None if no previous release.
            previous_revision: Revision of previously-released package (type
                depends on repo - see ReleaseVCS.get_current_revision().
            kwargs: Reserved.

        Note:
            This method should raise a `ReleaseHookCancellingError` if the
            release process should be cancelled.
        """
        pass

    def pre_release(self, user, install_path, variants=None,
                    release_message=None, changelog=None, previous_version=None,
                    previous_revision=None, **kwargs):
        """Pre-release hook.

        This is called before any package variants are released.

        Args:
            user: Name of person who did the release.
            install_path: Directory the package was installed into.
            variants: List of variant indices we are attempting to release, or
                None
            release_message: User-supplied release message.
            changelog: List of strings describing changes since last release.
            previous_version: Version object - previously-release package, or
                None if no previous release.
            previous_revision: Revision of previously-releaved package (type
                depends on repo - see ReleaseVCS.get_current_revision().
            kwargs: Reserved.

        Note:
            This method should raise a `ReleaseHookCancellingError` if the
            release process should be cancelled.
        """
        pass

    def post_release(self, user, install_path, variants, release_message=None,
                     changelog=None, previous_version=None,
                     previous_revision=None, **kwargs):
        """Post-release hook.

        This is called after all package variants have been released.

        Args:
            user: Name of person who did the release.
            install_path: Directory the package was installed into.
            variants (list of `Variant`): The variants that have been released.
            release_message: User-supplied release message.
            changelog: List of strings describing changes since last release.
            previous_version: Version of previously-release package, None if
                no previous release.
            previous_revision: Revision of previously-releaved package (type
                depends on repo - see ReleaseVCS.get_current_revision().
            kwargs: Reserved.
        """
        pass


class ReleaseHookEvent(Enum):
    """Enum to help manage release hooks."""
    pre_build = ("pre-build", "build", "pre_build")
    pre_release = ("pre-release", "release", "pre_release")
    post_release = ("post-release", "release", "post_release")

    def __init__(self, label, noun, func_name):
        self.label = label
        self.noun = noun
        self.__name__ = func_name


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
