"""
Prints package completion strings.
"""
from rez.vendor import argparse

__doc__ = argparse.SUPPRESS


def setup_parser(parser):
    parser.add_argument("-t", "--type", dest="type", type=str,
                        choices=("package", "config"),
                        help="type of completion")
    parser.add_argument("-c", "--command-line", dest="command_line",
                        metavar="VARIABLE", type=str,
                        help="assume the current command line is stored in "
                        "the given environment variable, and base completion "
                        "on this, rather than PREFIX")
    parser.add_argument("PREFIX", type=str, nargs='?',
                        help="prefix for completion")


def command(opts, parser):
    from rez.util import timings
    from rez.config import config

    words = []
    timings.enabled = False
    config.override("quiet", True)

    if opts.command_line:
        import os
        line = os.getenv(opts.command_line, '')
        toks = line.strip().split()
        if len(toks) > 1:
            prefix = toks[-1]
        else:
            prefix = ''
    else:
        prefix = opts.PREFIX or ''

    if opts.type == "package":
        from rez.packages import get_completions
        words = get_completions(prefix)
    elif opts.type == "config":
        words = config.get_completions(prefix)

    print ' '.join(words)
