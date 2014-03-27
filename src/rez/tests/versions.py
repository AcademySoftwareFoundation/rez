from rez.version_token import get_version_token_types, get_version_token_class
import unittest
import textwrap



class TestVersionSchema(unittest.TestCase):
    def __init__(self, fn, name):
        unittest.TestCase.__init__(self, fn)
        self.token_name = name
        self.token_cls = get_version_token_class(name)

    def _create_random_token(self):
        s = self.token_cls.create_random_token_string()
        return self.token_cls(s)

    def _test_token_strict_weak_ordering(self, tok1, tok2):
        self.assertTrue(tok1 == tok1)
        self.assertTrue(tok2 == tok2)

        e       = (tok1 == tok2)
        ne      = (tok1 != tok2)
        lt      = (tok1 < tok2)
        lte     = (tok1 <= tok2)
        gt      = (tok1 > tok2)
        gte     = (tok1 >= tok2)

        print '\n' + textwrap.dedent( \
            """
            %s %s
            e:    %s
            ne:   %s
            lt:   %s
            lte:  %s
            gt:   %s
            gte:  %s
            """).strip() % (tok1,tok2,e,ne,lt,lte,gt,gte)

        self.assertTrue(e != ne)
        if e:
            self.assertTrue(not lt)
            self.assertTrue(not gt)
            self.assertTrue(lte)
            self.assertTrue(gte)
        else:
            self.assertTrue(lt != gt)
            self.assertTrue(lte != gte)
            self.assertTrue(lt == lte)
            self.assertTrue(gt == gte)

    def test_create_token(self):
        print "\n\nTOKEN TYPE: %s" % self.token_name
        self._create_random_token()

    def test_token_strict_weak_ordering(self):
        # test equal tokens
        tok = self._create_random_token()
        self._test_token_strict_weak_ordering(tok, tok)

        # test random tokens
        for i in range(100):
            tok1 = self._create_random_token()
            tok2 = self._create_random_token()
            self._test_token_strict_weak_ordering(tok1, tok2)


def get_test_suites():
    suites = []
    for name in get_version_token_types():
        suite = unittest.TestSuite()
        suite.addTest(TestVersionSchema("test_create_token", name))
        suite.addTest(TestVersionSchema("test_token_strict_weak_ordering", name))
        suites.append(suite)
    return suites
