import sys
import os
import unittest
import utils
utils.setup_pythonpath()
import rez.config
import rez.rex as rex


class TestRex(utils.BaseUnitTest):
    def eval_package(self, version):
        orig_environ = os.environ.copy()
        pkg = 'rextest-%s' % version
        resolver = rez.config.Resolver()
        results = resolver.resolve([pkg])

        # the environment should not have changed yet.
        self.assertEqual(orig_environ, os.environ)

        found = False
        for pkg_res in results[0]:
            if pkg_res.name == 'rextest':
                found = True
                break
        assert found

        ref_commands = self.get_reference_commands(version)
        for command, ref_command in zip(pkg_res.commands, ref_commands):
            print>>sys.stderr, "real", command, command.args
            print>>sys.stderr, "ref ", ref_command, ref_command.args
            self.assertEqual(command, ref_command)

    def get_reference_commands(self, version):
        commands = []
        commands.append(rex.Comment(''))
        commands.append(rex.Comment('Commands from package rextest-%s' % version))
        commands.append(rex.Setenv('REZ_REXTEST_VERSION', version))
        commands.append(rex.Setenv('REZ_REXTEST_BASE', '%s/rextest/%s' % (self.release_path, version)))
        commands.append(rex.Setenv('REZ_REXTEST_ROOT', '%s/rextest/%s' % (self.release_path, version)))
        commands.append(rex.Setenv('REXTEST_ROOT', '%s/rextest/%s' % (self.release_path, version)))
        commands.append(rex.Setenv('REXTEST_VERSION', version))
        commands.append(rex.Setenv('REXTEST_MAJOR_VERSION', version.split('.')[0]))
        commands.append(rex.Setenv('REXTEST_DIRS', '%s/rextest/%s/%s/bin' % (self.release_path, version, version)))
        commands.append(rex.Alias('rextest', 'foobar'))
        return commands

    def test_yaml_old(self):
        self.eval_package('1.1')

    def test_yaml_new(self):
        self.eval_package('1.2')

    def test_py(self):
        self.eval_package('1.3')

class TestNamespaceFormatter(unittest.TestCase):

    def setUp(self):
        self.formatter = rex.NamespaceFormatter({})

    def assert_formatter_equal(self, format, expected, *args, **kwargs):

        self.assertEqual(self.formatter.format(format, *args, **kwargs), expected)

    def assert_formatter_raises(self, format, error, *args, **kwargs):

        self.assertRaises(error, self.formatter.format, format, *args, **kwargs)

    def test_formatter_rex(self):

        self.assert_formatter_equal('Hello, ${world}!', 'Hello, ${world}!')
        self.assert_formatter_equal('Hello, ${{world}}!', 'Hello, ${Earth}!', world="Earth")
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
        class C:
            def __init__(self, x=100):
                self._x = x
            def __format__(self, spec):
                return spec

        class D:
            def __init__(self, x):
                self.x = x
            def __format__(self, spec):
                return str(self.x)

        # class with __str__, but no __format__
        class E:
            def __init__(self, x):
                self.x = x
            def __str__(self):
                return 'E(' + self.x + ')'

        # class with __repr__, but no __format__ or __str__
        class F:
            def __init__(self, x):
                self.x = x
            def __repr__(self):
                return 'F(' + self.x + ')'

        # class with __format__ that forwards to string, for some format_spec's
        class G:
            def __init__(self, x):
                self.x = x
            def __str__(self):
                return "string is " + self.x
            def __format__(self, format_spec):
                if format_spec == 'd':
                    return 'G(' + self.x + ')'
                return object.__format__(self, format_spec)

        # class that returns a bad type from __format__
        class H:
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
        self.assert_formatter_equal('{0}', 'E(data)', E('data'))
        self.assert_formatter_equal('{0:^10}', ' E(data)  ', E('data'))
        self.assert_formatter_equal('{0:^10s}', ' E(data)  ', E('data'))
        self.assert_formatter_equal('{0:d}', 'G(data)', G('data'))
        self.assert_formatter_equal('{0:>15s}', ' string is data', G('data'))
        self.assert_formatter_equal('{0!s}', 'string is data', G('data'))

        self.assert_formatter_equal("{0:date: %Y-%m-%d}", "date: 2007-08-27", I(year=2007, month=8, day=27))

        # test deriving from a builtin type and overriding __format__
        self.assert_formatter_equal("{0}", "20", J(10))

        # string format specifiers
        self.assert_formatter_equal('{0:}', 'a', 'a')

        # computed format specifiers
        self.assert_formatter_equal("{0:.{1}}", 'hello', 'hello world', 5)
        self.assert_formatter_equal("{0:.{1}s}", 'hello', 'hello world', 5)
        self.assert_formatter_equal("{0:.{precision}s}", 'hello', 'hello world', precision=5)
        self.assert_formatter_equal("{0:{width}.{precision}s}", 'hello     ', 'hello world', width=10, precision=5)
        self.assert_formatter_equal("{0:{width}.{precision}s}", 'hello     ', 'hello world', width='10', precision='5')

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
        self.assert_formatter_raises("abc{0:{}", ValueError)
        self.assert_formatter_raises("{0", ValueError)
        self.assert_formatter_raises("{0.}", IndexError)
        self.assert_formatter_raises("{0.}", ValueError, 0)
        self.assert_formatter_raises("{0[}", IndexError)
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
        self.assert_formatter_raises("{:}", ValueError)
        self.assert_formatter_raises("{:s}", ValueError)
        self.assert_formatter_raises("{}", ValueError)

        # issue 6089
        self.assert_formatter_raises("{0[0]x}", ValueError, [None])
        self.assert_formatter_raises("{0[0](10)}", ValueError, [None])

        # can't have a replacement on the field name portion
        self.assert_formatter_raises('{0[{1}]}', TypeError, 'abcdefg', 4)

        # exceed maximum recursion depth
        self.assert_formatter_raises("{0:{1:{2}}}", ValueError, 'abc', 's', '')
        self.assert_formatter_raises("{0:{1:{2:{3:{4:{5:{6}}}}}}}", ValueError, 0, 1, 2, 3, 4, 5, 6, 7)

        # string format spec errors
        self.assert_formatter_raises("{0:-s}", ValueError, '')
        self.assert_formatter_raises("{0:=s}", ValueError, '')

if __name__ == '__main__':
    unittest.main()
