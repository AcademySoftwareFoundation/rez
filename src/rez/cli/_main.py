"""
The main command-line entry point.
"""
import os
import sys
import subprocess
from rez.vendor.argparse import _StoreTrueAction, SUPPRESS, ArgumentParser
from rez.cli._util import subcommands, LazyArgumentParser, _env_var_true
from rez.utils.logging_ import print_error
from rez.exceptions import RezError, RezSystemError
from rez.utils.logging_ import teed_call
from rez.config import config
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
    parser.add_argument("--profile", dest="profile", type=str,
                        help=SUPPRESS)
    parser.add_argument("--logfile", type=str,
                        help="direct all stdout and stderr ouput to the "
                             "given logfile, as well as the screen; will "
                             "override any logfile or logfile_by_command "
                             "settings in rezconfig, but will be ignored if "
                             "the --no-logfile flag is also present")
    parser.add_argument("--no-logfile", action='store_true',
                        help="disable the logfile, even if it is enabled due "
                             "to logfile or logfile_by_command settings in "
                             "rezconfig; will also override the --logfile "
                             "command line switch if both are present")


class InfoAction(_StoreTrueAction):
    def __call__(self, parser, args, values, option_string=None):
        from rez.system import system
        txt = system.get_summary_string()
        print
        print txt
        print
        sys.exit(0)


def run(command=None):
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

    # opts.no_logfile always wins, because this gives us an easy way to make
    # sure we're not recursively calling ourselves when logging is on...
    if not opts.no_logfile:
        logfile = opts.logfile
        if not logfile:
            # trying checking the rezconfig for this command...
            logfile = config.logfile_by_command.get(opts.cmd)

            # ...then try checking the global rezconfig logfile setting
            if not logfile:
                logfile = config.logfile

        # if we do logging, we relaunch as a subprocess, in which we 'tee' the
        # output to a file, but which is otherwise identical...
        if logfile:
            # first, make sure we add the '--no-logfile' arg, so we don't
            # recurse...
            new_args = list(sys.argv)
            new_args.insert(1, "--no-logfile")

            # turn off python buffering to get more accurate output ordering...
            environ = dict(os.environ)
            environ['PYTHONUNBUFFERED'] = '1'

            with open(logfile, 'w', buffering=4096) as logfile_handle:
                sys.exit(teed_call(new_args, stdout=logfile_handle,
                                   stderr=subprocess.STDOUT, env=environ))

    if opts.debug or _env_var_true("REZ_DEBUG"):
        exc_type = None
    else:
        exc_type = RezError

    def run_cmd():
        return opts.func(opts, opts.parser, arg_groups[1:])

    if opts.profile:
        import cProfile
        cProfile.runctx("run_cmd()", globals(), locals(), filename=opts.profile)
        returncode = 0
    else:
        try:
            returncode = run_cmd()
        except (NotImplementedError, RezSystemError) as e:
            raise
        except exc_type as e:
            print_error("%s: %s" % (e.__class__.__name__, str(e)))
            #print >> sys.stderr, "rez: %s: %s" % (e.__class__.__name__, str(e))
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
