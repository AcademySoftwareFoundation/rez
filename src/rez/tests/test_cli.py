# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test running of all commandline tools (just -h on each)
"""
from rez.tests.util import TestBase
import os.path
import subprocess
import unittest

from rez.system import system
from rez.cli._entry_points import get_specifications


class TestImports(TestBase):
    def test_1(self):
        """run -h option on every cli tool"""

        # skip if cli not available
        if not system.rez_bin_path:
            self.skipTest("Not a production install")

        for toolname in get_specifications().keys():
            if toolname.startswith('_'):
                continue

            binfile = os.path.join(system.rez_bin_path, toolname)
            subprocess.check_output([binfile, "-h"])


if __name__ == '__main__':
    unittest.main()
