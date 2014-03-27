from rez.backport.total_ordering import total_ordering
from rez.exceptions import VersionError
import re



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

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        return self.token



class AlphanumericVersionToken(VersionToken):
    """Alphanumeric version token.

    These tokens compare as follows:
    - each token is split into alpha and numeric groups (subtokens);
    - the resulting subtoken list is compared.

    Subtokens compare as follows:
    - numbers come before alphas;
    - alphas are compared alphabetically;
    - numbers are compared numerically;
    - if two numbers are equal, then their string form is compared. Thus,
      "01" is less than "1".

    Some example comparisons that equate to true:
    - "3" < "4"
    - "beta" < "1"
    - "alpha3" < "alpha4"
    - "alpha" < "alpha3"
    - "gamma33" < "33gamma"
    - "3build02" < "3build2"
    """
    numeric_regex = re.compile("[0-9]+")
    regex = re.compile(r"[a-zA-Z0-9_]+\Z")

    @classmethod
    def name(cls):
        return "alphanumeric"

    def __init__(self, token):
        super(AlphanumericVersionToken,self).__init__(token)

        if not self.regex.match(token):
            raise VersionError("Invalid version token: '%s'" % token)

        self.subtokens = []
        alphas = self.numeric_regex.split(token)
        numerics = self.numeric_regex.findall(token)
        b = True

        while alphas or numerics:
            if b:
                alpha = alphas[0]
                alphas = alphas[1:]
                if alpha:
                    self.subtokens.append(alpha)
            else:
                numeric = numerics[0]
                numerics = numerics[1:]
                self.subtokens.append((int(numeric), numeric))
            b = not b

    def less_than(self, other):
        return (self.subtokens < other.subtokens)



@total_ordering
class Version(object):
    """Version object.

    A Version is a sequence of zero or more version tokens, separated by either
    a dot '.' or hyphen '-' delimiters. A Version is constructed with a
    VersionToken class, so that different version schemas can be created. Note
    that separators only affect Version objects cosmetically - in other words,
    the version '1.0.0' is equivalent to '1-0-0'.
    """
    re_token = re.compile(r"[^\.\-]+")

    def __init__(self, ver_str='', token_cls=AlphanumericVersionToken):
        """Create a Version object.

        Args:
            ver_str: Version string. The empty string is a special case - this
                is the smallest possible version, and is used to represent
                unversioned objects.
            token_cls: Version token class to use.
        """
        self.ver_str = ver_str
        self.tokens = []
        self.seps = []

        if ver_str:
            toks = self.re_token.findall(ver_str)
            if not toks:
                raise VersionError(ver_str)

            seps = self.re_token.split(ver_str)
            if seps[0] or seps[-1] or max(len(x) for x in seps) > 1:
                raise VersionError("Invalid version syntax: '%s'" % ver_str)

            for tok in toks:
                try:
                    self.tokens.append(token_cls(tok))
                except VersionError as e:
                    raise VersionError("Invalid version '%s': %s"
                                       % (ver_str, str(e)))

            self.seps = seps[1:-1]

    def __eq__(self, other):
        return (self.tokens == other.tokens)

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        return (self.tokens < other.tokens)

    def __str__(self):
        return self.ver_str
