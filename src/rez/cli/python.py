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
Start a python interpreter or execute a python script within Rez's own execution context.

Unrecognised args are passed directly to the underlying python interpreter.
"""


def setup_parser(parser, completions=False):
    file_action = parser.add_argument(
        "FILE", type=str, nargs='?',
        help='python script to execute')

    if completions:
        from rez.cli._complete_util import FilesCompleter
        file_action.completer = FilesCompleter(dirs=False,
                                               file_patterns=["*.py"])


def command(opts, parser, extra_arg_groups=None):
    from rez.cli._main import is_hyphened_command
    from rez.utils.execution import Popen
    import sys

    # We need to skip first arg if 'rez-python' form was used, but we need to
    # skip the first TWO args if 'rez python' form was used.
    #
    if is_hyphened_command():
        args = sys.argv[1:]
    else:
        args = sys.argv[2:]

    cmd = [sys.executable, "-E"] + args

    with Popen(cmd) as p:
        sys.exit(p.wait())
