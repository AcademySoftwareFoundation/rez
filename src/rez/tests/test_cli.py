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
