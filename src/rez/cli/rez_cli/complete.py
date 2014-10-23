"""
Prints package completion strings.
"""
from rez.vendor import argparse

__doc__ = argparse.SUPPRESS


def setup_parser(parser, completions=False):
    pass


def command(opts, parser, extra_arg_groups=None):
    from rez.cli._complete_util import run
    run("rez")
