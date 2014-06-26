"""
Prints package completion strings.
"""
from rez.vendor import argparse

__doc__ = argparse.SUPPRESS


def setup_parser(parser):
    parser.add_argument("PREFIX", type=str, nargs='?',
                        help="prefix for completion")


def command(opts, parser):
    from rez.config import config
    from rez.packages import get_completions

    config.override("quiet", True)
    words = get_completions(opts.PREFIX or '')
    print ' '.join(words)
