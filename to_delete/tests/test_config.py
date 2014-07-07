import nose
from nose.tools import raises
import utils
utils.setup_pythonpath()
import rez.config
from rez.system import system
from rez.exceptions import PkgsUnresolvedError, PkgConfigNotResolvedError, PkgConflictError, PkgNotFoundError
from rez.public_enums import RESOLVE_MODE_LATEST, RESOLVE_MODE_EARLIEST

PLATFORM_PKG = "platform-" + system.platform
ARCH_PKG = "arch-" + system.arch


def check_basic_resolve(pkgs, assertions,
                        resolver_args=dict(resolve_mode=RESOLVE_MODE_LATEST),
                        resolve_args={}):
    resolver = rez.config.Resolver(**resolver_args)
    result = resolver.resolve(pkgs, **resolve_args)
    # TODO: reset cached resolves
    assert_resolve_result(result, [PLATFORM_PKG] + assertions + [ARCH_PKG])

def assert_resolve_result(result, assertions):
    assert result is not None
    pkg_ress, commands, dot_graph, num_fails = result

    res = [p.short_name() for p in pkg_ress]
    assert res == assertions, res


class TestResolve(utils.BaseTest):
    def setUp(self):
        utils.BaseTest.setUp(self)
        self.cleanup()

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
                          (['site'],
                           ['python-2.6.4', 'nuke-7.1.2', 'maya-2013', 'site']),
                          (['nuke-7'],
                           ['python-2.6.4', 'nuke-7.1.2']),
                          (['mtoa'],
                           ['python-2.7.4', 'maya-2014', 'arnold-4.0.16.0', 'mtoa-0.25.0']),
                          (['python', 'mercurial'],
                           ['python-2.7.4', 'mercurial-3.0']),
                          ([PLATFORM_PKG],
                           [])
                          ]:
            yield check_basic_resolve, ins, outs, dict(resolve_mode=RESOLVE_MODE_LATEST)
            yield check_basic_resolve, ins, outs, dict(resolve_mode=RESOLVE_MODE_LATEST,
                                                       assume_dt=True)

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

if machine.platform == 'linux':
    PYTHON_DIR = '/usr/local/python-{version}'
    PATH.prepend('$PYTHON_DIR/bin')
elif machine.platform == 'darwin':
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