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


import os.path
import subprocess


def set_authors(data):
    """Add 'authors' attribute based on repo contributions
    """
    if "authors" in data:
        return

    shfile = os.path.join(os.path.dirname(__file__), "get_committers.sh")

    p = subprocess.Popen(["bash", shfile], stdout=subprocess.PIPE)
    out, _ = p.communicate()
    if p.returncode:
        return

    authors = out.strip().split('\n')
    authors = [x.strip() for x in authors]

    data["authors"] = authors
