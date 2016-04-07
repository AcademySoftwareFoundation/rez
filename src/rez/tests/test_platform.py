"""
text platform
"""
import os
import sys

from rez.tests.util import TestBase
from rez.config import Config, get_module_root_config
import imp

from rez.utils.platform_ import Platform


class MockPlatform(Platform):
    """
    Platform that returns os and arch given in constructor
    As it overrides Platform the decorators still will kick-in.
    """

    def __init__(self, os, arch):
        self.mock_os = os
        self.mock_arch = arch

    def _os(self):
        return self.mock_os

    def _arch(self):
        return self.mock_arch


class MockConfigImporter(object):
    """
    In order to get different values we import all modules except for rez.config.
    In latter case the config from the constructor is returned.
    """

    modules__ = {}

    def __init__(self, config):
        self.config = config

    def find_module(self, module_name, package_path):
        self.modules__[module_name] = package_path[0]
        return self

    def load_module(self, module_name):
        if module_name == 'rez.config':
            return self

        with open(os.path.join(self.modules__[module_name], module_name.split('.')[-1]+".py"), "r") as fh:
            module = imp.load_module(module_name, fh, module_name+".py", ('.py','r', imp.PY_SOURCE))

        return module


class ConfigStub(object):

    def __init__(self, platform_map):
        self.platform_map = platform_map


class TestPlatformMap(TestBase):

    def setUp(self):
        if 'rez.config' in sys.modules:
            del sys.modules['rez.config']

    def tearDown(self):
        pass

    def test_os(self):
        """Test platform_map for os"""

        # overrides set to bad types
        platform_map = {
            "os": {
                r"An Linux": "Changed",
                r"Something Linux-(.*)": r"Changed-\1",
            },
            "arch": {
                "amd_64": "Changed",
                "x(86)_(\d)": r"Changed-\1-\2"
            }
        }

        # Use MockConfigImporter and replace our config.platform_map
        sys.meta_path.append(MockConfigImporter(ConfigStub(platform_map)))

        # This is probably already cached, so reload.
        import rez.utils.platform_ as rez_platform
        reload(rez_platform)

        # Test platform_map
        l = MockPlatform('An Linux', 'amd_64')
        self.assertEqual(l.os, 'Changed', 'Replacing os')
        self.assertEqual(l.arch, 'Changed', 'Replacing arch')

        l = MockPlatform('Something Linux-3.2', 'x86_64')
        self.assertEqual(l.os, 'Changed-3.2', 'Regular expressions on os')
        self.assertEqual(l.arch, 'Changed-86-64', 'Regular expressions on arch')

        l = MockPlatform('Not in dict', 'arm')
        self.assertEqual(l.os, 'Not in dict', 'Not in dict')
        self.assertEqual(l.arch, 'arm', 'Not in dict')

