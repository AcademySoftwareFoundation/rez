"""
baz plugin
"""

from rez.command import Command

# This attribute is optional, default behavior will be applied if not present.
command_behavior = {
    "hidden": False,  # (bool): default False
    "arg_mode": None,  # (str): "passthrough", "grouped", default None
}


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-m", "--message", action="store_true", help="Print message from world."
    )


def command(opts, parser=None, extra_arg_groups=None):
    from baz import core

    if opts.message:
        msg = core.get_message_from_baz()
        print(msg)
        return

    print("Please use '-h' flag to see what you can do to this world !")


class BazCommand(Command):
    @classmethod
    def name(cls):
        return "baz_cmd"


def register_plugin():
    return BazCommand
