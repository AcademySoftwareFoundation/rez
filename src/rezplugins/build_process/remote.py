"""
Builds packages on remote hosts
"""
from rez.build_process import BuildProcessHelper


class RemoteBuildProcess(BuildProcessHelper):
    """The default build process.

    This process builds a package's variants sequentially, on remote hosts.
    """
    @classmethod
    def name(cls):
        return "remote"

    def build(self, install_path=None, clean=False, install=False, variants=None):
        raise NotImplementedError("coming soon...")

    def release(self, release_message=None, variants=None):
        raise NotImplementedError("coming soon...")


def register_plugin():
    return RemoteBuildProcess


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
