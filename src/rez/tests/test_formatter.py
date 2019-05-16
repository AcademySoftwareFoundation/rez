"""
test rex string formatting
"""
import unittest
from rez.tests.util import TestBase
from rez.rex import NamespaceFormatter
import sys

PY2 = sys.version_info[0] == 2


class TestFormatter(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        self.formatter = NamespaceFormatter({})

    def assert_formatter_equal(self, format, expected, *args, **kwargs):
        self.assertEqual(self.formatter.format(format, *args, **kwargs), expected)

    def assert_formatter_raises(self, format, error, *args, **kwargs):
        self.assertRaises(error, self.formatter.format, format, *args, **kwargs)

    def test_formatter_rex(self):
        self.assert_formatter_equal('Hello, ${world}!', 'Hello, ${world}!')
        self.assert_formatter_equal('Hello, $WORLD!', 'Hello, ${WORLD}!')
        self.assert_formatter_equal('Hello, ${{world}}!', 'Hello, ${world}!', world="Earth")
        self.assert_formatter_equal('Hello, {world}!', 'Hello, Earth!', world="Earth")

    def test_formatter_stdlib(self):
        """
        string.Formatter.format tests from the Python standard library used to
        ensure we haven't broken functionality preset in the standard
        implementation of the Formatter object.
        """
        self.assert_formatter_equal('', '')
        self.assert_formatter_equal('a', 'a')
        self.assert_formatter_equal('ab', 'ab')
        self.assert_formatter_equal('a{{', 'a{')
        self.assert_formatter_equal('a}}', 'a}')
        self.assert_formatter_equal('{{b', '{b')
        self.assert_formatter_equal('}}b', '}b')
        self.assert_formatter_equal('a{{b', 'a{b')

        # examples from the PEP:
        import datetime
        self.assert_formatter_equal("My name is {0}", "My name is Fred", 'Fred')
        self.assert_formatter_equal("My name is {0[name]}", "My name is Fred", dict(name='Fred'))
        self.assert_formatter_equal("My name is {0} :-{{}}", "My name is Fred :-{}", 'Fred')

        d = datetime.date(2007, 8, 18)
        self.assert_formatter_equal("The year is {0.year}", "The year is 2007", d)

        # classes we'll use for testing
        class C(object):
            def __init__(self, x=100):
                self._x = x
            def __format__(self, spec):
                return spec

        class D(object):
            def __init__(self, x):
                self.x = x
            def __format__(self, spec):
                return str(self.x)

        # class with __str__, but no __format__
        class E(object):
            def __init__(self, x):
                self.x = x
            def __str__(self):
                return 'E(' + self.x + ')'

        # class with __repr__, but no __format__ or __str__
        class F(object):
            def __init__(self, x):
                self.x = x
            def __repr__(self):
                return 'F(' + self.x + ')'

        # class with __format__ that forwards to string, for some format_spec's
        class G(object):
            def __init__(self, x):
                self.x = x
            def __str__(self):
                return "string is " + self.x
            def __format__(self, format_spec):
                if format_spec == 'd':
                    return 'G(' + self.x + ')'
                return object.__format__(self, format_spec)

        # class that returns a bad type from __format__
        class H(object):
            def __format__(self, format_spec):
                return 1.0

        class I(datetime.date):
            def __format__(self, format_spec):
                return self.strftime(format_spec)

        class J(int):
            def __format__(self, format_spec):
                return int.__format__(self * 2, format_spec)

        self.assert_formatter_equal('', '')
        self.assert_formatter_equal('abc', 'abc')
        self.assert_formatter_equal('{0}', 'abc', 'abc')
        self.assert_formatter_equal('{0:}', 'abc', 'abc')
        self.assert_formatter_equal('X{0}', 'Xabc', 'abc')
        self.assert_formatter_equal('{0}X', 'abcX', 'abc')
        self.assert_formatter_equal('X{0}Y', 'XabcY', 'abc')
        self.assert_formatter_equal('{1}', 'abc', 1, 'abc')
        self.assert_formatter_equal('X{1}', 'Xabc', 1, 'abc')
        self.assert_formatter_equal('{1}X', 'abcX', 1, 'abc')
        self.assert_formatter_equal('X{1}Y', 'XabcY', 1, 'abc')
        self.assert_formatter_equal('{0}', '-15', -15)
        self.assert_formatter_equal('{0}{1}', '-15abc', -15, 'abc')
        self.assert_formatter_equal('{0}X{1}', '-15Xabc', -15, 'abc')
        self.assert_formatter_equal('{{', '{')
        self.assert_formatter_equal('}}', '}')
        self.assert_formatter_equal('{{}}', '{}')
        self.assert_formatter_equal('{{x}}', '{x}')
        self.assert_formatter_equal('{{{0}}}', '{123}', 123)
        self.assert_formatter_equal('{{{{0}}}}', '{{0}}')
        self.assert_formatter_equal('}}{{', '}{')
        self.assert_formatter_equal('}}x{{', '}x{')

        # weird field names
        self.assert_formatter_equal("{0[foo-bar]}", 'baz', {'foo-bar':'baz'})
        self.assert_formatter_equal("{0[foo bar]}", 'baz', {'foo bar':'baz'})
        self.assert_formatter_equal("{0[ ]}", '3', {' ':3})

        self.assert_formatter_equal('{foo._x}', '20', foo=C(20))
        self.assert_formatter_equal('{1}{0}', '2010', D(10), D(20))
        self.assert_formatter_equal('{0._x.x}', 'abc', C(D('abc')))
        self.assert_formatter_equal('{0[0]}', 'abc', ['abc', 'def'])
        self.assert_formatter_equal('{0[1]}', 'def', ['abc', 'def'])
        self.assert_formatter_equal('{0[1][0]}', 'def', ['abc', ['def']])
        self.assert_formatter_equal('{0[1][0].x}', 'def', ['abc', [D('def')]])

        # strings
        self.assert_formatter_equal('{0:.3s}', 'abc', 'abc')
        self.assert_formatter_equal('{0:.3s}', 'ab', 'ab')
        self.assert_formatter_equal('{0:.3s}', 'abc', 'abcdef')
        self.assert_formatter_equal('{0:.0s}', '', 'abcdef')
        self.assert_formatter_equal('{0:3.3s}', 'abc', 'abc')
        self.assert_formatter_equal('{0:2.3s}', 'abc', 'abc')
        self.assert_formatter_equal('{0:2.2s}', 'ab', 'abc')
        self.assert_formatter_equal('{0:3.2s}', 'ab ', 'abc')
        self.assert_formatter_equal('{0:x<0s}', 'result', 'result')
        self.assert_formatter_equal('{0:x<5s}', 'result', 'result')
        self.assert_formatter_equal('{0:x<6s}', 'result', 'result')
        self.assert_formatter_equal('{0:x<7s}', 'resultx', 'result')
        self.assert_formatter_equal('{0:x<8s}', 'resultxx', 'result')
        self.assert_formatter_equal('{0: <7s}', 'result ', 'result')
        self.assert_formatter_equal('{0:<7s}', 'result ', 'result')
        self.assert_formatter_equal('{0:>7s}', ' result', 'result')
        self.assert_formatter_equal('{0:>8s}', '  result', 'result')
        self.assert_formatter_equal('{0:^8s}', ' result ', 'result')
        self.assert_formatter_equal('{0:^9s}', ' result  ', 'result')
        self.assert_formatter_equal('{0:^10s}', '  result  ', 'result')
        self.assert_formatter_equal('{0:10000}', 'a' + ' ' * 9999, 'a')
        self.assert_formatter_equal('{0:10000}', ' ' * 10000, '')
        self.assert_formatter_equal('{0:10000000}', ' ' * 10000000, '')

        # format specifiers for user defined type
        self.assert_formatter_equal('{0:abc}', 'abc', C())

        # !r and !s coersions
        self.assert_formatter_equal('{0!s}', 'Hello', 'Hello')
        self.assert_formatter_equal('{0!s:}', 'Hello', 'Hello')
        self.assert_formatter_equal('{0!s:15}', 'Hello          ', 'Hello')
        self.assert_formatter_equal('{0!s:15s}', 'Hello          ', 'Hello')
        self.assert_formatter_equal('{0!r}', "'Hello'", 'Hello')
        self.assert_formatter_equal('{0!r:}', "'Hello'", 'Hello')
        self.assert_formatter_equal('{0!r}', 'F(Hello)', F('Hello'))

        # test fallback to object.__format__
        self.assert_formatter_equal('{0}', '{}', {})
        self.assert_formatter_equal('{0}', '[]', [])
        self.assert_formatter_equal('{0}', '[1]', [1])

        if PY2:
            # Classes without __format__ are not supported in Python 3
            self.assert_formatter_equal('{0}', 'E(data)', E('data'))
            self.assert_formatter_equal('{0:^10}', ' E(data)  ', E('data'))
            self.assert_formatter_equal('{0:^10s}', ' E(data)  ', E('data'))
            self.assert_formatter_equal('{0:>15s}', ' string is data', G('data'))

        self.assert_formatter_equal('{0:d}', 'G(data)', G('data'))
        self.assert_formatter_equal('{0!s}', 'string is data', G('data'))

        self.assert_formatter_equal("{0:date: %Y-%m-%d}", "date: 2007-08-27",
                                    I(year=2007, month=8, day=27))

        # test deriving from a builtin type and overriding __format__
        self.assert_formatter_equal("{0}", "20", J(10))

        # string format specifiers
        self.assert_formatter_equal('{0:}', 'a', 'a')

        # computed format specifiers
        self.assert_formatter_equal("{0:.{1}}", 'hello', 'hello world', 5)
        self.assert_formatter_equal("{0:.{1}s}", 'hello', 'hello world', 5)
        self.assert_formatter_equal("{0:.{precision}s}", 'hello', 'hello world',
                                    precision=5)
        self.assert_formatter_equal("{0:{width}.{precision}s}", 'hello     ',
                                    'hello world', width=10, precision=5)
        self.assert_formatter_equal("{0:{width}.{precision}s}", 'hello     ',
                                    'hello world', width='10', precision='5')

        # test various errors
        self.assert_formatter_raises('{', ValueError)
        self.assert_formatter_raises('}', ValueError)
        self.assert_formatter_raises('a{', ValueError)
        self.assert_formatter_raises('a}', ValueError)
        self.assert_formatter_raises('{a', ValueError)
        self.assert_formatter_raises('}a', ValueError)
        self.assert_formatter_raises('{0}', IndexError)
        self.assert_formatter_raises('{1}', IndexError, 'abc')
        self.assert_formatter_raises('{x}', KeyError)
        self.assert_formatter_raises("}{", ValueError)
        self.assert_formatter_raises("{", ValueError)
        self.assert_formatter_raises("}", ValueError)
        self.assert_formatter_raises(r"abc{0:{}", ValueError)
        self.assert_formatter_raises("{0", ValueError)
        self.assert_formatter_raises("{0.}", IndexError)
        self.assert_formatter_raises("{0.}", ValueError, 0)

        if PY2:
            self.assert_formatter_raises("{0[}", IndexError)
        else:
            self.assert_formatter_raises("{0[}", ValueError)

        self.assert_formatter_raises("{0[}", ValueError, [])
        self.assert_formatter_raises("{0]}", KeyError)
        self.assert_formatter_raises("{0.[]}", ValueError, 0)
        self.assert_formatter_raises("{0..foo}", ValueError, 0)
        self.assert_formatter_raises("{0[0}", ValueError, 0)
        self.assert_formatter_raises("{0[0:foo}", ValueError, 0)
        self.assert_formatter_raises("{c]}", KeyError)
        self.assert_formatter_raises("{{ {{{0}}", ValueError, 0)
        self.assert_formatter_raises("{0}}", ValueError, 0)
        self.assert_formatter_raises("{foo}", KeyError, bar=3)
        self.assert_formatter_raises("{0!x}", ValueError, 3)
        self.assert_formatter_raises("{0!}", ValueError, 0)
        self.assert_formatter_raises("{0!rs}", ValueError, 0)
        self.assert_formatter_raises("{!}", ValueError)

        # in python 2.7 onwards, string.Formatter raises KeyError here, rather
        # than ValueError. In rex we keep this as ValueError (the change is due
        # to implicit positional arguments, not applicable in rex).
        if PY2:
            self.assert_formatter_raises("{:}", ValueError)
            self.assert_formatter_raises("{:s}", ValueError)
            self.assert_formatter_raises("{}", ValueError)
        else:
            self.assert_formatter_raises("{:}", IndexError)
            self.assert_formatter_raises("{:s}", IndexError)
            self.assert_formatter_raises("{}", IndexError)

        # issue 6089
        self.assert_formatter_raises("{0[0]x}", ValueError, [None])
        self.assert_formatter_raises("{0[0](10)}", ValueError, [None])

        # can't have a replacement on the field name portion
        self.assert_formatter_raises('{0[{1}]}', TypeError, 'abcdefg', 4)

        # exceed maximum recursion depth
        self.assert_formatter_raises("{0:{1:{2}}}", ValueError, 'abc', 's', '')
        self.assert_formatter_raises("{0:{1:{2:{3:{4:{5:{6}}}}}}}",
                                     ValueError, 0, 1, 2, 3, 4, 5, 6, 7)

        # string format spec errors
        self.assert_formatter_raises("{0:-s}", ValueError, '')
        self.assert_formatter_raises("{0:=s}", ValueError, '')

    def test_formatter_recurse(self):
        self.assert_formatter_equal('Hello {0}!', 'Hello Earth!', '{world}',
                                    world='Earth')

        self.assert_formatter_equal('Hello {greeted}!', 'Hello Timmy the Trex!',
                                    greeted='{dinosaur}', person='{Bob}',
                                    Bob='Fabulous Bobby', dinosaur='{Trex}',
                                    Trex='Timmy the Trex')
        self.formatter.namespace.update(greeted='{dinosaur}', person='{Bob}',
                                        Bob='Fabulous Bobby', dinosaur='{Trex}',
                                        Trex='Timmy the Trex')
        self.assert_formatter_equal('Hello {greeted}!',
                                    'Hello Timmy the Trex!')



if __name__ == '__main__':
    unittest.main()


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
