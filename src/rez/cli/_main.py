"""
The main command-line entry point.
"""
import os
import sys
from rez.vendor.argparse import _StoreTrueAction, SUPPRESS
from rez.cli._util import subcommands, LazyArgumentParser, _env_var_true
from rez import __version__


class SetupRezSubParser(object):
    """Callback class for lazily setting up rez sub-parsers."""
    def __init__(self, module_name):
        self.module_name = module_name

    def __call__(self, parser_name, parser):
        mod = self.get_module()

        error_msg = None
        if not mod.__doc__:
            error_msg = "command module %s must have a module-level " \
                "docstring (used as the command help)" % self.module_name
        if not hasattr(mod, 'command'):
            error_msg = "command module %s must provide a command() " \
                "function" % self.module_name
        if not hasattr(mod, 'setup_parser'):
            error_msg = "command module %s  must provide a setup_parser() " \
                "function" % self.module_name
        if error_msg:
            print >> sys.stderr, error_msg
            return SUPPRESS

        mod.setup_parser(parser)
        parser.description = mod.__doc__
        parser.set_defaults(func=mod.command, parser=parser)
        # add the common args to the subparser
        _add_common_args(parser)

        # optionally, return the brief help line for this sub-parser
        brief = mod.__doc__.strip('\n').split('\n')[0]
        return brief

    def get_module(self):
        if self.module_name not in sys.modules:
            __import__(self.module_name, globals(), locals(), [], -1)
        return sys.modules[self.module_name]


def _add_common_args(parser):
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="verbose mode, repeat for more verbosity")
    parser.add_argument("--debug", dest="debug", action="store_true",
                        help=SUPPRESS)
    parser.add_argument("--debug-tmpdir", dest="debug_tmpdir",
                        action="store_true", help=SUPPRESS)


class InfoAction(_StoreTrueAction):
    def __call__(self, parser, args, values, option_string=None):
        print
        print "Rez %s" % __version__
        print
        from rez.plugin_managers import plugin_manager
        print plugin_manager.get_summary_string()
        print
        sys.exit(0)


def run(command=None):
    import rez.cli
    parser = LazyArgumentParser("rez")

    parser.add_argument("-i", "--info", action=InfoAction,
                        help="print information about rez and exit")
    parser.add_argument("-V", "--version", action="version",
                        version="Rez %s" % __version__)

    # add args common to all subcommands... we add them both to the top parser,
    # AND to the subparsers, for two reasons:
    #  1) this allows us to do EITHER "rez --debug build" OR
    #     "rez build --debug"
    #  2) this allows the flags to be used when using either "rez" or
    #     "rez-build" - ie, this will work: "rez-build --debug"
    _add_common_args(parser)

    # add lazy subparsers
    subparser = parser.add_subparsers(dest='cmd', metavar='COMMAND')
    for subcommand in subcommands:
        module_name = "rez.cli.%s" % subcommand
        subparser.add_parser(
            subcommand,
            help='',  # required so that it can be setup later
            setup_subparser=SetupRezSubParser(module_name))

    # parse args, but split extras into groups separated by "--"
    all_args = ([command] + sys.argv[1:]) if command else sys.argv[1:]
    arg_groups = [[]]
    for arg in all_args:
        if arg == '--':
            arg_groups.append([])
            continue
        arg_groups[-1].append(arg)
    opts = parser.parse_args(arg_groups[0])

    if opts.debug or _env_var_true("REZ_DEBUG"):
        exc_type = None
    else:
        exc_type = Exception

    if opts.debug_tmpdir or _env_var_true("REZ_DEBUG_TMPDIR"):
        from rez.util import set_rm_tmpdirs
        set_rm_tmpdirs(False)

    try:
        returncode = opts.func(opts, opts.parser, arg_groups[1:])
    except NotImplementedError as e:
        import traceback
        raise Exception(traceback.format_exc())
    except exc_type as e:
        print >> sys.stderr, "rez: %s: %s" % (e.__class__.__name__, str(e))
        sys.exit(1)

    sys.exit(returncode or 0)


if __name__ == '__main__':
    run()
