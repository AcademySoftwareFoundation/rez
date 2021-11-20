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
Demoing Rez's command type plugin
"""
from rez.command import Command

# This attribute is optional, default behavior will be applied if not present.
command_behavior = {
    "hidden": False,   # (bool): default False
    "arg_mode": None,  # (str): "passthrough", "grouped", default None
}


def setup_parser(parser, completions=False):
    parser.add_argument("-m", "--message", action="store_true",
                        help="Print message from world.")


def command(opts, parser=None, extra_arg_groups=None):
    from hello_cmd import lib

    if opts.message:
        msg = lib.get_message_from_world()
        print(msg)
        return

    print("Please use '-h' flag to see what you can do to this world !")


class WorldCommand(Command):

    @classmethod
    def name(cls):
        return "world"


def register_plugin():
    return WorldCommand
