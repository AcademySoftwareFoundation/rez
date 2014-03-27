from rez import plugin_factory
from rez.version_token import VersionToken
import re



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

    @classmethod
    def name(cls):
        return "alphanumeric"

    def __init__(self, token):
        super(AlphanumericVersionToken,self).__init__(token)
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


class AlphanumericVersionTokenFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return AlphanumericVersionToken
