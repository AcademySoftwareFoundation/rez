from rez.vendor.argparse import _StoreTrueAction
from rez import __version__
import sys


class InfoAction(_StoreTrueAction):
    def __call__(self, parser, args, values, option_string=None):
        print
        print "Rez %s" % __version__
        print
        from rez.plugin_managers import plugin_manager
        print plugin_manager.get_summary_string()
        print
        sys.exit(0)


def add_top_level_arguments(parser):
    parser.add_argument(
        "-i", "--info", action=InfoAction,
        help="print information about rez and exit")
    parser.add_argument(
        "-V", "--version", action="version",
        version="Rez %s" % __version__)
