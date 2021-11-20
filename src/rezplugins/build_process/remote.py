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
