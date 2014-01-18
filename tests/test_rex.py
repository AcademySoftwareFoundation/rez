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

if __name__ == '__main__':
    unittest.main()
