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
Binds rez itself as a rez package.
"""
from __future__ import absolute_import
import rez
from rez.package_maker import make_package
from rez.bind._utils import check_version
from rez.system import system
from rez.utils.lint_helper import env
import shutil
import os.path


def commands():
    env.PYTHONPATH.append('{this.root}')


def bind(path, version_range=None, opts=None, parser=None):
    version = rez.__version__
    check_version(version, version_range)

    def make_root(variant, root):
        # copy source
        rez_path = rez.__path__[0]
        site_path = os.path.dirname(rez_path)
        rezplugins_path = os.path.join(site_path, "rezplugins")

        shutil.copytree(rez_path, os.path.join(root, "rez"))
        shutil.copytree(rezplugins_path, os.path.join(root, "rezplugins"))

    with make_package("rez", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.commands = commands
        pkg.requires = ["python-2.7+<4"]
        pkg.variants = [system.variant]

    return pkg.installed_variants
