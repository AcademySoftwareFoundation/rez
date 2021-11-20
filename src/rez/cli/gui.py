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
Run the Rez GUI application.
"""


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--diff", nargs=2, metavar=("RXT1", "RXT2"),
        help="open in diff mode with the given contexts")
    FILE_action = parser.add_argument(
        "FILE", type=str, nargs='*',
        help="context files")

    if completions:
        from rez.cli._complete_util import FilesCompleter
        FILE_action.completer = FilesCompleter()


def command(opts, parser=None, extra_arg_groups=None):
    from rezgui.app import run
    run(opts, parser)
