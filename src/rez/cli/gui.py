"""Run the Rez GUI application."""


def setup_parser(parser, completions=False):
    pass


def command(opts, parser=None, extra_arg_groups=None):
    from rezgui.app import run
    run()
