# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for 'utils.py23' module
"""
import os
import sys
import tempfile

from rez.tests.util import TestBase
from rez.utils import py23


class TestLoadModuleFromFile(TestBase):
    def test_load_module(self):
        """Ensure that the imported module does not show up in sys.modules"""
        # Random chars are used in the module name to ensure that the module name is unique
        # and the test won't fail because some other module with the same name
        # shows up in sys.modules
        module = 'utils_test_7cd3a335'

        filename = '{0}.py'.format(module)
        tmpdir = tempfile.mkdtemp(prefix="rez_selftest_")

        with open(os.path.join(tmpdir, filename), 'w') as fd:
            fd.write('')

        py23.load_module_from_file(
            module,
            os.path.join(tmpdir, filename)
        )
        self.assertEqual(sys.modules.get(module), None, msg='Module was found in sys.modules')
