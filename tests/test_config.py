import nose
from nose.tools import raises
import utils
utils.setup_pythonpath()
import rez.rez_config
from rez.rez_config import Resolver
from rez.rez_exceptions import PkgsUnresolvedError, PkgConfigNotResolvedError, PkgConflictError, PkgNotFoundError
from rez.public_enums import RESOLVE_MODE_LATEST, RESOLVE_MODE_EARLIEST
from rez.rez_filesys import _g_os_pkg as OS_PKG
from rez.rez_filesys import _g_arch_pkg as ARCH_PKG

def check_basic_resolve(pkgs, assertions,
                        resolver_args=dict(resolve_mode=RESOLVE_MODE_LATEST),
                        resolve_args={}):
    resolver = rez.rez_config.Resolver(**resolver_args)
    result = resolver.resolve(pkgs, **resolve_args)
    # TODO: reset cached resolves
    assert_resolve_result(result, [OS_PKG] + assertions + [ARCH_PKG])

def assert_resolve_result(result, assertions):
    assert result is not None
    pkg_ress, commands, dot_graph, num_fails = result

    res = [p.short_name() for p in pkg_ress]
    assert res == assertions, res

class ResolveBaseTest(utils.BaseTest):
    def setUp(self):
        self.cleanup()
        self.add_packages()
        self.make_packages()

    def add_packages(self):
        # real world examples are so much easier to follow
        with self.add_package('python-2.7.4', local=True) as pkg:
            pkg.variants = [['platform-linux'],
                            ['platform-darwin']]

        with self.add_package('python-2.6.4') as pkg:
            pkg.variants = [['platform-linux'],
                            ['platform-darwin']]

        with self.add_package('python-2.6.1') as pkg:
            pkg.variants = [['platform-linux'],
                            ['platform-darwin']]

        with self.add_package('maya-2012') as pkg:
            pkg.requires = ['python-2.6']

        with self.add_package('maya-2013') as pkg:
            pkg.requires = ['python-2.6']

        with self.add_package('maya-2014') as pkg:
            pkg.requires = ['python-2.7']

        with self.add_package('nuke-7.1.2') as pkg:
            pkg.requires = ['python-2.6']

        with self.add_package('arnold-4.0.16.0') as pkg:
            pkg.requires = ['python']

        with self.add_package('mtoa-0.25.0') as pkg:
            pkg.requires = ['arnold-4.0.16']
            pkg.variants = [['maya-2014'], ['maya-2013']]

        self.add_package('platform-linux')
        self.add_package('platform-darwin')

        self.add_package('arch-x86_64')
        self.add_package('arch-i386')

class TestResolve(ResolveBaseTest):
    def test_latest(self):
        for ins, outs in [
                          (['python'],
                           ['python-2.7.4']),
                          (['python-2.6'],
                           ['python-2.6.4']),
                          (['maya'],
                           ['python-2.7.4', 'maya-2014']),
                          (['maya', 'python-2.6'],
                           ['python-2.6.4', 'maya-2013']),
                          (['maya', 'nuke-7'],
                           ['python-2.6.4', 'nuke-7.1.2', 'maya-2013']),
                          (['nuke-7'],
                           ['python-2.6.4', 'nuke-7.1.2']),
                          (['mtoa'],
                           ['python-2.7.4', 'maya-2014', 'arnold-4.0.16.0', 'mtoa-0.25.0']),
                          ([OS_PKG],
                           [])
                          ]:
            yield check_basic_resolve, ins, outs

    def test_earliest(self):
        for ins, outs in [(['python'],
                           ['python-2.6.1']),
                          (['python-2.6'],
                           ['python-2.6.1']),
                          (['maya'],
                           ['python-2.6.1', 'maya-2012']),
                          (['maya', 'python-2.6'],
                           ['python-2.6.1', 'maya-2012']),
                          (['maya', 'nuke'],
                           ['python-2.6.1', 'nuke-7.1.2', 'maya-2012']),
                          ]:
            yield check_basic_resolve, ins, outs, dict(resolve_mode=RESOLVE_MODE_EARLIEST)

    def test_failures(self):
        for ins, exc in [(['python-2.7', 'python-2.6'], PkgConflictError), # straight conflict
                         (['nuke-6'], PkgNotFoundError), # does not exist
                         # I dont understand the practical difference between
                         # PkgsUnresolvedError and PkgConfigNotResolvedError
                         (['maya-2014', 'nuke-7'], PkgConfigNotResolvedError),
                         (['maya-2014', 'nuke-7+'], PkgConfigNotResolvedError),
                         ]:
            # `raises` is a decorator that returns a modified test function that
            # passes the test if the exception is raised
            yield raises(exc)(check_basic_resolve), ins, None

class TestCommands(TestResolve):
    PYTHON_COMMANDS = '''
REZ_PYTHON_MAJOR_VERSION = '{version.part(1)}'
REZ_PYTHON_MINOR_VERSION = '{version.part(2)}'

if machine.os == 'Linux':
    PYTHON_DIR = '/usr/local/python-{version}'
    PATH.prepend('$PYTHON_DIR/bin')
elif machine.os == 'Darwin':
    PYTHON_DIR = '/usr/local/python-{version}'
    PATH.prepend('$PYTHON_DIR/Python.framework/Versions/{version.thru(2)}/bin')
else:
    PYTHON_DIR = 'C:/Python{version.part(1)}{version.part(2)}'
    PATH.prepend('$PYTHON_DIR')
    PATH.prepend('$PYTHON_DIR/Scripts')'''

    def add_packages(self):
        super(TestCommands, self).add_packages()
        # overrides:
        with self.add_package('python-2.7.4', local=True) as pkg:
            pkg.variants = [['platform-linux'],
                            ['platform-darwin']]
            # new style:
            pkg.commands = self.PYTHON_COMMANDS

        with self.add_package('python-2.6.4') as pkg:
            pkg.variants = [['platform-linux'],
                            ['platform-darwin']]
            # new style:
            pkg.commands = self.PYTHON_COMMANDS

        with self.add_package('arnold-4.0.16.0') as pkg:
            pkg.requires = ['python']
            # old-style:
            pkg.commands = ['export CMAKE_MODULE_PATH=!ROOT!/cmake:$CMAKE_MODULE_PATH'
                            'export ARNOLD_HOME=/usr/local/solidAngle/arnold-!VERSION!'
                            'export PATH=$ARNOLD_HOME/bin:$PATH'
                            'export PYTHONPATH=$ARNOLD_HOME/python:$PYTHONPATH']

    def test_commands(self):
        for ins, outs in [
                          (['python'],
                           ['python-2.7.4']),
                          (['python-2.6'],
                           ['python-2.6.4']),
                          (['mtoa'],
                           ['python-2.7.4', 'maya-2014', 'arnold-4.0.16.0', 'mtoa-0.25.0']),
                          ]:
            yield check_basic_resolve, ins, outs

if __name__ == '__main__':
    nose.main()