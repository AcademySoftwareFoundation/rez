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


from __future__ import print_function

import rez
from rez.package_maker import make_package
from rez.system import system
import os.path
import sys
import shutil


def install_as_rez_package(repo_path):
    """Install the current rez installation as a rez package.

    Note: This is very similar to 'rez-bind rez', however rez-bind is intended
    for deprecation. Rez itself is a special case.

    Args:
        repo_path (str): Repository to install the rez package into.
    """
    def commands():
        env.PYTHONPATH.append('{this.root}')  # noqa

    def make_root(variant, root):
        # copy source
        rez_path = rez.__path__[0]
        site_path = os.path.dirname(rez_path)
        rezplugins_path = os.path.join(site_path, "rezplugins")

        shutil.copytree(rez_path, os.path.join(root, "rez"))
        shutil.copytree(rezplugins_path, os.path.join(root, "rezplugins"))

    variant = system.variant
    variant.append("python-{0.major}.{0.minor}".format(sys.version_info))

    with make_package("rez", repo_path, make_root=make_root) as pkg:
        pkg.version = rez.__version__
        pkg.commands = commands
        pkg.variants = [variant]

    print('')
    print("Success! Rez was installed to %s/rez/%s" % (repo_path, rez.__version__))
