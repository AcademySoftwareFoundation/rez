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


from rez.config import config


class Command(object):
    """An interface for registering custom Rez subcommand

    To register plugin and expose subcommand, the plugin module..

    * MUST have a module-level docstring (used as the command help)
    * MUST provide a `setup_parser()` function
    * MUST provide a `command()` function
    * MUST provide a `register_plugin()` function
    * SHOULD have a module-level attribute `command_behavior`

    For example, a plugin named 'foo' and this is the `foo.py`:

        '''The docstring for command help, this is required.
        '''
        from rez.command import Command

        command_behavior = {
            "hidden": False,   # optional: bool
            "arg_mode": None,  # optional: None, "passthrough", "grouped"
        }

        def setup_parser(parser, completions=False):
            parser.add_argument("--hello", ...)

        def command(opts, parser=None, extra_arg_groups=None):
            if opts.hello:
                print("world")

        class CommandFoo(Command):
            schema_dict = {}

            @classmethod
            def name(cls):
                return "foo"

        def register_plugin():
            return CommandFoo

    """
    def __init__(self):
        self.type_settings = config.plugins.extension
        self.settings = self.type_settings.get(self.name())

    @classmethod
    def name(cls):
        """Return the name of the Command and rez-subcommand."""
        raise NotImplementedError
