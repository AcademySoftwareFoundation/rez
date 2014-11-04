from rez.vendor.argparse import _StoreTrueAction
from rez import __version__
import sys


class ShellCodeAction(_StoreTrueAction):
    def __call__(self, parser, args, values, option_string=None):
        from soma.production_config import ProductionConfig

        pc = ProductionConfig.get_current_config()
        print pc.shell_code()
        sys.exit(0)


def add_top_level_arguments(parser):
    parser.add_argument(
        "--sh", "--shell-code", dest="shell_code", action=ShellCodeAction,
        help="print shell code to activate the current soma configuration")
