"""
Prints package completion strings.
"""
from rez.vendor import argparse

__doc__ = argparse.SUPPRESS


def setup_parser(parser):
    parser.add_argument("--type", type=str, choices=("package", "config"),
                        help="type of completion")
    parser.add_argument("PREFIX", type=str, nargs='?',
                        help="prefix for completion")


def command(opts, parser):
    from rez.util import timings
    from rez.config import config

    words = []
    timings.enabled = False
    config.override("quiet", True)

    if opts.type == "packages":
        from rez.packages import get_completions
        words = get_completions(opts.PREFIX or '')
    elif opts.type == "config":
        words = config.get_completions(opts.PREFIX or '')

    print ' '.join(words)
