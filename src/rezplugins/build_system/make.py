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
