from rez.version import Version, AlphanumericVersionToken
from rez.tests.util import _test_strict_weak_ordering
import unittest
import random
import textwrap



class TestVersionSchema(unittest.TestCase):
    token_cls = AlphanumericVersionToken

    def __init__(self, fn):
        unittest.TestCase.__init__(self, fn)

    def _test_strict_weak_ordering(self, a, b):
        self.assertTrue(a == a)
        self.assertTrue(b == b)

        e       = (a == b)
        ne      = (a != b)
        lt      = (a < b)
        lte     = (a <= b)
        gt      = (a > b)
        gte     = (a >= b)

        print '\n' + textwrap.dedent( \
            """
            '%s' <op> '%s'
            ==:  %s
            !=:  %s
            <:   %s
            <=:  %s
            >:   %s
            >=:  %s
            """).strip() % (a,b,e,ne,lt,lte,gt,gte)

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

    def _test_ordered(self, items):
        def _test(fn, items_, op_str):
            for i,a in enumerate(items_):
                for b in items_[i+1:]:
                    print "'%s' %s '%s'" % (a, op_str, b)
                    self.assertTrue(fn(a,b))

        _test(lambda a,b:a<b, items, '<')
        _test(lambda a,b:a<=b, items, '<=')
        _test(lambda a,b:a!=b, items, '!=')
        _test(lambda a,b:a>b, list(reversed(items)), '>')
        _test(lambda a,b:a>=b, list(reversed(items)), '>=')
        _test(lambda a,b:a!=b, list(reversed(items)), '!=')

    def _create_random_token(self):
        s = self.token_cls.create_random_token_string()
        return AlphanumericVersionToken(s)

    def _create_random_version(self):
        ver_str = '.'.join(self.token_cls.create_random_token_string() \
            for i in range(random.randint(0,6)))
        return Version(ver_str, token_cls=self.token_cls)

    def test_token_strict_weak_ordering(self):
        # test equal tokens
        tok = self._create_random_token()
        self._test_strict_weak_ordering(tok, tok)

        # test random tokens
        for i in range(100):
            tok1 = self._create_random_token()
            tok2 = self._create_random_token()
            self._test_strict_weak_ordering(tok1, tok2)

    def test_version_strict_weak_ordering(self):
        # test equal versions
        ver = self._create_random_version()
        self._test_strict_weak_ordering(ver, ver)

        # test random versions
        for i in range(100):
            ver1 = self._create_random_version()
            ver2 = self._create_random_version()
            self._test_strict_weak_ordering(ver1, ver2)

    def test_token_comparisons(self):
        def _lt(a, b):
            print "'%s' < '%s'" % (a, b)
            self.assertTrue(self.token_cls(a) < self.token_cls(b))
            self.assertTrue(Version(a) < Version(b))

        print
        _lt("3", "4")
        _lt("beta", "1")
        _lt("alpha3", "alpha4")
        _lt("alpha", "alpha3")
        _lt("gamma33", "33gamma")

    def test_version_comparisons(self):
        def _eq(a, b):
            print "'%s' == '%s'" % (a, b)
            self.assertTrue(Version(a) == Version(b))

        print
        _eq("", "")
        _eq("1", "1")
        _eq("1.2", "1-2")
        _eq("1.2-3", "1-2.3")

        ascending = ["",
                     "0.0.0",
                     "1",
                     "2",
                     "2.alpha1",
                     "2.alpha2",
                     "2.beta",
                     "2.0",
                     "2.0.8.8",
                     "2.1",
                     "2.1.0"]
        self._test_ordered([Version(x) for x in ascending])


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestVersionSchema("test_token_strict_weak_ordering"))
    suite.addTest(TestVersionSchema("test_version_strict_weak_ordering"))
    suite.addTest(TestVersionSchema("test_token_comparisons"))
    suite.addTest(TestVersionSchema("test_version_comparisons"))
    suites.append(suite)
    return suites
