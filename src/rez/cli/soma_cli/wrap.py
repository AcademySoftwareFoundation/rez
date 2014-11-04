"""
Executes a command in a profile.
"""


from rez.vendor import argparse

__doc__ = argparse.SUPPRESS


def setup_parser(parser, completions=False):
    parser.add_argument("PROFILE", type=str)


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from soma.production_config import ProductionConfig
    from soma.exceptions import SomaNotFoundError
    from soma.wrapper import Wrapper
    import sys

    def _error():
        parser.error("expected: soma wrap PROFILE -- COMMAND --")

    if len(extra_arg_groups) != 2:
        _error()
    if not extra_arg_groups[0]:
        _error()

    pc = ProductionConfig.get_current_config()

    try:
        profile = pc.profile(opts.PROFILE)
    except SomaNotFoundError:
        print >> sys.stderr, "The tool's profile %r does not exist" % opts.PROFILE
        sys.exit(112)  # reserved for stale tool error code

    command = extra_arg_groups[0]
    args = extra_arg_groups[1]
    wrapper = Wrapper(profile, command)
    returncode = wrapper.run(*args)
    sys.exit(returncode)
