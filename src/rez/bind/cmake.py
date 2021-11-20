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
Binds a cmake executable as a rez package.
"""
from __future__ import absolute_import
from rez.package_maker import make_package
from rez.bind._utils import check_version, find_exe, extract_version, make_dirs
from rez.utils.platform_ import platform_
from rez.system import system
from rez.utils.lint_helper import env
import os.path


def setup_parser(parser):
    parser.add_argument("--exe", type=str, metavar="PATH",
                        help="manually specify the cmake executable to bind.")


def commands():
    env.PATH.append('{this.root}/bin')


def bind(path, version_range=None, opts=None, parser=None):
    exepath = find_exe("cmake", getattr(opts, "exe", None))
    version = extract_version(exepath, "--version",
                              word_index=2 if os.name == 'nt' else -1)
    check_version(version, version_range)

    def make_root(variant, root):
        binpath = make_dirs(root, "bin")
        link = os.path.join(binpath, "cmake")
        platform_.symlink(exepath, link)

    with make_package("cmake", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.tools = ["cmake"]
        pkg.commands = commands
        pkg.variants = [system.variant]

    return pkg.installed_variants
