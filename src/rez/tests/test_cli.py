# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
