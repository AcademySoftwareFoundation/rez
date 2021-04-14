"""
The main command-line entry point.
"""
from __future__ import print_function

import sys
import importlib
from argparse import _StoreTrueAction, SUPPRESS
from rez.cli._util import subcommands, LazyArgumentParser, _env_var_true
from rez.utils.logging_ import print_error
from rez.exceptions import RezError, RezSystemError, _NeverError
from rez import __version__


# true if command was like 'rez-env' rather than 'rez env'
_hyphened_command = False


def is_hyphened_command():
    return _hyphened_command


class SetupRezSubParser(object):
    """Callback class for lazily setting up rez sub-parsers.
    """
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
            print(error_msg, file=sys.stderr)
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
            importlib.import_module(self.module_name)
        return sys.modules[self.module_name]


def _add_common_args(parser):
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="verbose mode, repeat for more verbosity")
    parser.add_argument("--debug", dest="debug", action="store_true",
                        help=SUPPRESS)
    parser.add_argument("--profile", dest="profile", type=str,
                        help=SUPPRESS)


class InfoAction(_StoreTrueAction):
    def __call__(self, parser, args, values, option_string=None):
        from rez.system import system
        txt = system.get_summary_string()
        print()
        print(txt)
        print()
        sys.exit(0)


def setup_parser():
    """Create and setup parser for given rez command line interface.

    Returns:
        LazyArgumentParser: Argument parser for rez command.
    """
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
    for subcommand, data in subcommands.items():
        module_name = data.get('module_name', 'rez.cli.%s' % subcommand)

        subparser.add_parser(
            subcommand,
            help='',  # required so that it can be setup later
            setup_subparser=SetupRezSubParser(module_name))

    return parser


def run(command=None):
    global _hyphened_command

    sys.dont_write_bytecode = True

    # construct args list. Note that commands like 'rez-env foo' and
    # 'rez env foo' are equivalent
    #
    if command:
        # like 'rez-foo arg1 arg2'
        args = [command] + sys.argv[1:]
        _hyphened_command = True
    elif len(sys.argv) > 1 and sys.argv[1] in subcommands:
        # like 'rez foo arg1 arg2'
        command = sys.argv[1]
        args = sys.argv[1:]
    else:
        # like 'rez -i'
        args = sys.argv[1:]

    # parse args depending on subcommand behaviour
    if command:
        arg_mode = subcommands[command].get("arg_mode")
    else:
        arg_mode = None

    parser = setup_parser()
    if arg_mode == "grouped":
        # args split into groups by '--'
        arg_groups = [[]]
        for arg in args:
            if arg == '--':
                arg_groups.append([])
                continue
            arg_groups[-1].append(arg)

        opts = parser.parse_args(arg_groups[0])
        extra_arg_groups = arg_groups[1:]
    elif arg_mode == "passthrough":
        # unknown args passed in first extra_arg_group
        opts, extra_args = parser.parse_known_args(args)
        extra_arg_groups = [extra_args]
    else:
        # native arg parsing
        opts = parser.parse_args(args)
        extra_arg_groups = []

    if opts.debug or _env_var_true("REZ_DEBUG"):
        exc_type = _NeverError
    else:
        exc_type = RezError

    def run_cmd():
        try:
            # python3 will not automatically handle cases where no sub parser
            # has been selected. In these cases func will not exist, and an
            # AttributeError will be raised.
            func = opts.func
        except AttributeError:
            parser.error("too few arguments.")
        else:
            return func(opts, opts.parser, extra_arg_groups)

    if opts.profile:
        import cProfile
        cProfile.runctx("run_cmd()", globals(), locals(), filename=opts.profile)
        returncode = 0
    else:
        try:
            returncode = run_cmd()
        except (NotImplementedError, RezSystemError):
            raise
        except exc_type as e:
            print_error("%s: %s" % (e.__class__.__name__, str(e)))
            sys.exit(1)

    sys.exit(returncode or 0)


if __name__ == '__main__':
    run()


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
