"""
Make-based build system
"""
from rez.build_system import BuildSystem
import os.path


class MakeBuildSystem(BuildSystem):
    @classmethod
    def name(cls):
        return "make"

    @classmethod
    def is_valid_root(cls, path, package=None):
        return os.path.isfile(os.path.join(path, "Makefile"))

    def __init__(self, working_dir, opts=None, package=None, write_build_scripts=False,
                 verbose=False, build_args=[], child_build_args=[]):
        super(MakeBuildSystem, self).__init__(working_dir)
        raise NotImplementedError


def register_plugin():
    return MakeBuildSystem


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
