"""Version number submodule."""
from rez.backport.total_ordering import total_ordering



def get_version_token_types():
    """Returns the available version token implementations."""
    from rez.plugin_managers import version_schema_plugin_manager
    return version_schema_plugin_manager().get_plugins()


def get_version_token_class(name=None):
    """Return the VersionToken class registered under this plugin name."""
    from rez.plugin_managers import version_schema_plugin_manager
    if name is None:
        from rez.settings import settings
        name = settings.version_schema
    return version_schema_plugin_manager().get_plugin_class(name)


@total_ordering
class VersionToken(object):
    """Token within a version number.

    A version token is that part of a version number that appears between a
    delimiter, typically '.' or '-'. For example, the version number '2.3.7'
    contains the tokens '2', '3' and '7' respectively.

    Version tokens are only allowed to contain alphanumerics (any case) and
    underscores.
    """

    # Set to False if your tokens may match. even if their strings differ. For
    # example, you might ignore number padding, so "01" and "1" would be equal.
    string_equivalence = True

    @classmethod
    def name(cls):
        """Return the name of the version token type."""
        raise NotImplementedError

    @classmethod
    def create_random_token_string(cls):
        """Create a random token string.

        This is used for testing purposes only. The default implementation
        returns a random combination of alphanumerics and underscores.
        """
        chars = \
            [chr(x) for x in range(ord('a'),ord('z')+1)] + \
            [chr(x) for x in range(ord('A'),ord('Z')+1)] + \
            [chr(x) for x in range(ord('0'),ord('9')+1)] + \
            ['_']
        import random
        return ''.join([chars[random.randint(0, len(chars)-1)] for i in range(16)])

    def __init__(self, token):
        """Create a VersionToken.

        Args:
            token: Token string, eg "rc02"
        """
        self.token = token

    def less_than(self, other):
        """Compare to another VersionToken.

        VersionTokens have 'strict weak ordering' - that is, all other operators
        (>, <= etc) are implemented in terms of less-than.

        Args:
            other: The VersionToken object to compare against.

        Returns:
            True if this token is less than other, False otherwise.
        """
        raise NotImplementedError

    def __lt__(self, other):
        return self.less_than(other)

    def __eq__(self, other):
        return (self.token == other.token) if self.string_equivalence \
            else ((not self.less_than(other)) and (not other.less_than(self)))

    def __str__(self):
        return self.token
