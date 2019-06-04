from rez.vendor.version.version import Version, AlphanumericVersionToken, \
    VersionRange, reverse_sort_key, _ReversedComparable
from rez.vendor.version.requirement import Requirement, RequirementList
from rez.vendor.version.util import VersionError
import random
import textwrap
import unittest



def _print(txt=''):
    # uncomment for verbose output
    #print txt
    pass


class TestVersionSchema(unittest.TestCase):
    make_token = AlphanumericVersionToken

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

        _print('\n' + textwrap.dedent(
               """
               '%s' <op> '%s'
               ==:  %s
               !=:  %s
               <:   %s
               <=:  %s
               >:   %s
               >=:  %s
               """).strip() % (a, b, e, ne, lt, lte, gt, gte))

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

        if not isinstance(a, _ReversedComparable):
            self._test_strict_weak_ordering(reverse_sort_key(a),
                                            reverse_sort_key(b))

    def _test_ordered(self, items):
        def _test(fn, items_, op_str):
            for i, a in enumerate(items_):
                for b in items_[i+1:]:
                    _print("'%s' %s '%s'" % (a, op_str, b))
                    self.assertTrue(fn(a, b))

        _test(lambda a, b: a < b, items, '<')
        _test(lambda a, b: a <= b, items, '<=')
        _test(lambda a, b: a != b, items, '!=')
        _test(lambda a, b: a > b, list(reversed(items)), '>')
        _test(lambda a, b: a >= b, list(reversed(items)), '>=')
        _test(lambda a, b: a != b, list(reversed(items)), '!=')

    def _create_random_token(self):
        s = self.make_token.create_random_token_string()
        return self.make_token(s)

    def _create_random_version(self):
        ver_str = '.'.join(self.make_token.create_random_token_string()
                           for i in range(random.randint(0, 6)))
        return Version(ver_str, make_token=self.make_token)

    def test_misc(self):
        self.assertEqual(Version("1.2.12").as_tuple(), ("1", "2", "12"))

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
            _print("'%s' < '%s'" % (a, b))
            self.assertTrue(self.make_token(a) < self.make_token(b))
            self.assertTrue(Version(a) < Version(b))

        _print()
        _lt("3", "4")
        _lt("01", "1")
        _lt("beta", "1")
        _lt("alpha3", "alpha4")
        _lt("alpha", "alpha3")
        _lt("gamma33", "33gamma")

    def test_version_comparisons(self):
        def _eq(a, b):
            _print("'%s' == '%s'" % (a, b))
            self.assertTrue(Version(a) == Version(b))

        _print()
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

        def _eq2(a, b):
            _print("'%s' == '%s'" % (a, b))
            self.assertTrue(a == b)

        # test behaviour in sets
        a = Version("1.0")
        b = Version("1.0")
        c = Version("1.0alpha")
        d = Version("2.0.0")

        _eq2(set([a]) - set([a]), set())
        _eq2(set([a]) - set([b]), set())
        _eq2(set([a, a]) - set([a]), set())
        _eq2(set([b, c, d]) - set([a]), set([c, d]))
        _eq2(set([b, c]) | set([c, d]), set([b, c, d]))
        _eq2(set([b, c]) & set([c, d]), set([c]))

    def test_version_range(self):
        def _eq(a, b):
            _print("'%s' == '%s'" % (a, b))
            a_range = VersionRange(a)
            b_range = VersionRange(b)

            self.assertTrue(a_range == b_range)
            self.assertTrue(a_range.issuperset(a_range))
            self.assertTrue(a_range.issuperset(b_range))
            self.assertTrue(VersionRange(str(a_range)) == a_range)
            self.assertTrue(VersionRange(str(b_range)) == a_range)
            self.assertTrue(hash(a_range) == hash(b_range))

            a_ = a.replace('.', '-')
            a_ = a_.replace("--", "..")
            a_range_ = VersionRange(a_)
            self.assertTrue(a_range_ == a_range)
            self.assertTrue(hash(a_range_) == hash(a_range))

            range_strs = a.split('|')
            ranges = [VersionRange(x) for x in range_strs]
            ranges_ = ranges[0].union(ranges[1:])
            self.assertTrue(ranges_ == a_range)

            self.assertTrue(a_range | b_range == a_range)
            self.assertTrue(a_range - b_range is None)
            self.assertTrue(b_range - a_range is None)
            self.assertTrue(VersionRange() & a_range == a_range)
            self.assertTrue(b_range.span() & a_range == a_range)

            a_inv = a_range.inverse()
            self.assertTrue(a_inv == ~b_range)

            if a_inv:
                self.assertTrue(~a_inv == a_range)
                self.assertTrue(a_range | a_inv == VersionRange())
                self.assertTrue(a_range & a_inv is None)

            a_ranges = a_range.split()
            a_range_ = a_ranges[0].union(a_ranges[1:])
            self.assertTrue(a_range_ == b_range)

        def _and(a, b, c):
            _print("'%s' & '%s' == '%s'" % (a, b, c))
            a_range = VersionRange(a)
            b_range = VersionRange(b)
            c_range = None if c is None else VersionRange(c)
            self.assertTrue(a_range & b_range == c_range)
            self.assertTrue(b_range & a_range == c_range)

            a_or_b = a_range | b_range
            a_and_b = a_range & b_range
            a_sub_b = a_range - b_range
            b_sub_a = b_range - a_range
            ranges = [a_and_b, a_sub_b, b_sub_a]
            ranges = [x for x in ranges if x]
            self.assertTrue(ranges[0].union(ranges[1:]) == a_or_b)

        def _inv(a, b):
            a_range = VersionRange(a)
            b_range = VersionRange(b)
            self.assertTrue(~a_range == b_range)
            self.assertTrue(~b_range == a_range)
            self.assertTrue(a_range | b_range == VersionRange())
            self.assertTrue(a_range & b_range is None)

        # simple cases
        _print()
        _eq("", "")
        _eq("1", "1")
        _eq("1.0.0", "1.0.0")
        _eq("3+<3_", "3")
        _eq("_+<__", "_")
        _eq("1.2+<=2.0", "1.2..2.0")
        _eq("10+,<20", "10+<20")
        _eq("1+<1.0", "1+<1.0")
        _eq(">=2", "2+")
        _eq(">=1.21.1,<1.23", ">=1.21.1<1.23")
        _eq(">1.21.1,<1.23", ">1.21.1<1.23")
        _eq(">1.21.1<1.23", ">1.21.1<1.23")
        _eq(">1.21.1,<=1.23", ">1.21.1<=1.23")

        # Reverse order which is a syntax pip packages use more often now.
        # Only allowed when separated by a comma.
        _eq("<1.23,>=1.21.1", ">=1.21.1<1.23")
        _eq("<1.23,>1.21.1", ">1.21.1<1.23")

        # optimised cases
        _eq("3|3", "3")
        _eq("3|1", "1|3")
        _eq("5|3|1", "1|3|5")
        _eq("1|1_", "1+<1__")
        _eq("1|1_|1__", "1+,<1___")
        _eq("|", "")
        _eq("||", "||||||||")
        _eq("1|1_+", "1+")
        _eq("<1|1", "<1_")
        _eq("1+<3|3+<5", "1+<5")
        _eq(">4<6|1+<3", "1+<3|>4,<6")
        _eq("4+<6|1+<3|", "")
        _eq("4|2+", "2+")
        _eq("3|<5", "<5")
        _eq("<3|>3", ">3|<3")
        _eq("3+|<3", "")
        _eq("3+|<4", "")
        _eq("2+<=6|3+<5", "2..6")
        _eq("3+,<5|2+<=6", "2+<=6")
        _eq("2|2+", "2+")
        _eq("2|2.1+", "2+")
        _eq("2|<2.1", "<2_")
        _eq("3..3", "==3")
        _eq(">=3,<=3", "==3")

        # AND'ing
        _and("3", "3", "3")
        _and("1", "==1", "==1")
        _and("", "==1", "==1")
        _and("3", "4", None)
        _and("<3", "5+", None)
        _and("4+<6", "6+<8", None)
        _and("2+", "<=4", "2..4")
        _and("1", "1.0", "1.0")
        _and("4..6", "6+<8", "==6")

        # inverse
        _inv("3+", "<3")
        _inv("<=3", ">3")
        _inv("3.5", "<3.5|3.5_+")
        self.assertTrue(~VersionRange() is None)

        # odd (but valid) cases
        _eq(">", ">")       # greater than the empty version
        _eq("+", "")        # greater or equal to empty version (is all vers)
        _eq(">=", "")       # equivalent to above
        _eq("<=", "==")     # less or equal to empty version (is only empty)
        _eq("..", "==")     # from empty version to empty version
        _eq("+<=", "==")    # equivalent to above

        invalid_range = [
            "4+<2",         # lower bound greater than upper
            ">3<3",         # both greater and less than same version
            ">3<=3",        # greater and less or equal to same version
            "3+<3"          # greater and equal to, and less than, same version
        ]

        for s in invalid_range:
            self.assertRaises(VersionError, VersionRange, s)

        invalid_syntax = [
            "<",            # less than the empty version
            "><",           # both greater and less than empty version
            ">3>4",         # both are lower bounds
            "<3<4",         # both are upper bounds
            "<4>3",         # upper bound before lower without comma
            ",<4",          # leading comma
            "4+,",          # trailing comma
            "1>=",          # pre-lower-op in post
            "+1",           # post-lower-op in pre
            "4<",           # pre-upper-op in post
            "1+<2<3"        # more than two bounds
        ]

        for s in invalid_syntax:
            self.assertRaises(VersionError, VersionRange, s)

        # test simple logic
        self.assertTrue(VersionRange("").is_any())
        self.assertTrue(VersionRange("2+<4").bounded())
        self.assertTrue(VersionRange("2+").lower_bounded())
        self.assertTrue(not VersionRange("2+").upper_bounded())
        self.assertTrue(not VersionRange("2+").bounded())
        self.assertTrue(VersionRange("<2").upper_bounded())
        self.assertTrue(not VersionRange("<2").lower_bounded())
        self.assertTrue(not VersionRange("<2").bounded())

        # test range from version(s)
        v = Version("3")
        self.assertTrue(VersionRange.from_version(v, "eq") == VersionRange("==3"))
        self.assertTrue(VersionRange.from_version(v, "gt") == VersionRange(">3"))
        self.assertTrue(VersionRange.from_version(v, "gte") == VersionRange("3+"))
        self.assertTrue(VersionRange.from_version(v, "lt") == VersionRange("<3"))
        self.assertTrue(VersionRange.from_version(v, "lte") == VersionRange("<=3"))

        range1 = VersionRange.from_version(Version("2"), "gte")
        range2 = VersionRange.from_version(Version("4"), "lte")
        _eq(str(range1 & range2), "2..4")

        v2 = Version("6.0")
        v3 = Version("4")
        self.assertTrue(VersionRange.from_versions([v, v2, v3])
                        == VersionRange("==3|==4|==6.0"))

        # test behaviour in sets
        def _eq2(a, b):
            _print("'%s' == '%s'" % (a, b))
            self.assertTrue(a == b)

        a = VersionRange("1+<=2.5")
        b = VersionRange("1..2.5")
        c = VersionRange(">=5")
        d = VersionRange(">6.1.0")
        e = VersionRange("3.2")

        _eq2(set([a]) - set([a]), set())
        _eq2(set([a]) - set([b]), set())
        _eq2(set([a, a]) - set([a]), set())
        _eq2(set([b, c, d, e]) - set([a]), set([c, d, e]))
        _eq2(set([b, c, e]) | set([c, d]), set([b, c, d, e]))
        _eq2(set([b, c]) & set([c, d]), set([c]))

    def test_containment(self):
        # basic containment
        self.assertTrue(Version("3") in VersionRange("3+"))
        self.assertTrue(Version("5") in VersionRange("3..5"))
        self.assertTrue(Version("5_") not in VersionRange("3..5"))
        self.assertTrue(Version("3.0.0") in VersionRange("3+"))
        self.assertTrue(Version("3.0.0") not in VersionRange("3.1+"))
        self.assertTrue(Version("3") in VersionRange("<1|5|6|8|7|3|60+"))
        self.assertTrue(Version("3") in VersionRange("<1|5|6|8|7|==3|60+"))
        self.assertTrue(VersionRange("2.1+<4") in VersionRange("<4"))
        self.assertTrue(VersionRange("2.1..4") not in VersionRange("<4"))
        self.assertTrue(VersionRange("3") in VersionRange("3"))
        self.assertTrue(VersionRange("==3") in VersionRange("3"))
        self.assertTrue(VersionRange("3.5+<3_") in VersionRange("3"))
        self.assertTrue(VersionRange("3") not in VersionRange("4+<6"))
        self.assertTrue(VersionRange("3+<10") not in VersionRange("4+<6"))

        # iterating over sorted version list
        numbers = [2, 3, 5, 10, 11, 13, 14]
        versions = [Version(str(x)) for x in numbers]
        rev_versions = list(reversed(versions))
        composite_range = VersionRange.from_versions(versions)

        entries = [(VersionRange(""), 7),
                   (VersionRange("0+"), 7),
                   (VersionRange("5+"), 5),
                   (VersionRange("6+"), 4),
                   (VersionRange("50+"), 0),
                   (VersionRange(">5"), 4),
                   (VersionRange("5"), 1),
                   (VersionRange("6"), 0),
                   (VersionRange("<5"), 2),
                   (VersionRange("<6"), 3),
                   (VersionRange("<50"), 7),
                   (VersionRange("<=5"), 3),
                   (VersionRange("<1"), 0),
                   (VersionRange("2|9+"), 5),
                   (VersionRange("3+<6|12+<13.5"), 3),
                   (VersionRange("<1|20+"), 0),
                   (VersionRange(">0<20"), 7)]

        for range_, count in entries:
            # brute-force containment tests
            matches = set(x for x in versions if x in range_)
            self.assertEqual(len(matches), count)

            # more optimal containment tests
            def _test_it(it):
                matches_ = set(version for contains, version in it if contains)
                self.assertEqual(matches_, matches)

            _test_it(range_.iter_intersect_test(versions))
            _test_it(range_.iter_intersect_test(rev_versions, descending=True))

            # throw in an intersection test
            self.assertEqual(composite_range.intersects(range_), (count != 0))
            int_range = composite_range & range_
            versions_ = [] if int_range is None else int_range.to_versions()
            self.assertEqual(set(versions_), matches)

            # throw in a superset test as well
            self.assertEqual(range_.issuperset(composite_range), (count == 7))
            if count:
                self.assertTrue(composite_range.issuperset(int_range))

    def test_requirement_list(self):
        def _eq(reqs, expected_reqs):
            _print("requirements(%s) == requirements(%s)"
                   % (' '.join(reqs), ' '.join(expected_reqs)))
            reqs_ = [Requirement(x) for x in reqs]
            reqlist = RequirementList(reqs_)
            _print("result: %s" % str(reqlist))

            exp_reqs_ = [Requirement(x) for x in expected_reqs]
            self.assertTrue(reqlist.requirements == exp_reqs_)

            exp_names = set(x.name for x in exp_reqs_ if not x.conflict)
            self.assertTrue(reqlist.names == exp_names)

            exp_confl_names = set(x.name for x in exp_reqs_ if x.conflict)
            self.assertTrue(reqlist.conflict_names == exp_confl_names)

        def _confl(reqs, a, b):
            _print("requirements(%s) == %s <--!--> %s" % (' '.join(reqs), a, b))
            reqs_ = [Requirement(x) for x in reqs]
            reqlist = RequirementList(reqs_)
            _print("result: %s" % str(reqlist))

            a_req = Requirement(a)
            b_req = Requirement(b)
            self.assertTrue(reqlist.conflict == (a_req, b_req))

        _print()
        _eq(["foo"],
            ["foo"])
        _eq(["foo", "bah"],
            ["foo", "bah"])
        _eq(["bah", "foo"],
            ["bah", "foo"])
        _eq(["foo-4+", "foo-4.5"],
            ["foo-4.5"])
        _eq(["bah-2.4", "foo", "bah-2.4.1+"],
            ["bah-2.4.1+<2.4_", "foo"])
        _eq(["foo-2+", "!foo-4+"],
            ["foo-2+<4"])
        _eq(["!bah-1", "!bah-3"],
            ["!bah-1|3"])
        _eq(["!bah-5", "foo-2.3", "!bah-5.6+"],
            ["!bah-5+", "foo-2.3"])
        _eq(["~bah-4", "foo", "bah<4.2"],
            ["bah-4+<4.2", "foo"])
        _eq(["~bah", "!foo", "bah<4.2"],
            ["bah<4.2", "!foo"])
        _eq(["~bah-3+", "~bah-5"],
            ["~bah-5"])

        _confl(["foo-1", "foo-2"],
               "foo-1", "foo-2")
        _confl(["foo-2", "foo-1"],
               "foo-2", "foo-1")
        _confl(["foo", "~bah-5+", "bah-2"],
               "~bah-5+", "bah-2")
        _confl(["foo", "~bah-5+", "bah-7..12", "bah-2"],
               "bah-7..12", "bah-2")


if __name__ == '__main__':
    unittest.main()
