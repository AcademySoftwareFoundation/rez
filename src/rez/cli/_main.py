"""
The main command-line entry point.
"""
import sys
from rez.vendor.argparse import _StoreTrueAction, SUPPRESS
from rez.cli._util import subcommands, LazyArgumentParser, _env_var_true
from rez.exceptions import RezError, RezSystemError, CallbackAbort
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
    parser.add_argument("--pre-callback",
                        help="python code to execute before the command is "
                             "run; you raise a CallbackAbort to signal that"
                             "the command should not be run (other "
                             "exceptions will also cancel the command, "
                             "but will also print a traceback). The callback "
                             "is executed in a context where the following "
                             "names are available: opts - the parsed "
                             "command-line options; arg_groups - the args, "
                             "separated into different groups by '--' "
                             "characters; CallbackAbort - the error to "
                             "raise to signal early termination, provided "
                             "in the namespace for convenience")
    parser.add_argument("--post-callback",
                        help="python code to execute after the command is "
                             "run; the command obviously can't be "
                             "cancelled, but you may still raise a "
                             "CallbackAbort to cause the command to return "
                             "a non-zero exitcode if desired. The callback "
                             "is executed in a context with all the "
                             "names available in the pre-callback, "
                             "in addition to the following: returncode - the "
                             "returncode of the command, if it completed "
                             "successfully, and None if it did not; "
                             "error - None if the command completed "
                             "succesfully, and the exception instance if it "
                             "did not. Note that for commands which can "
                             "start interactive shells, such as rez-env, "
                             "this command will not be run until after the "
                             "shell exits")


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
    parser.add_argument

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
        exc_type = RezError

    pre_callback = opts.pre_callback
    if pre_callback is None:
        pre_callback = config.pre_callbacks.get(opts.cmd)
    post_callback = opts.post_callback
    if post_callback is None:
        post_callback = config.post_callbacks.get(opts.cmd)

    if post_callback is not None or pre_callback is not None:
        callback_globals = dict(__builtins__)
        callback_globals['opts'] = opts
        callback_globals['arg_groups'] = arg_groups
        callback_globals['CallbackAbort'] = CallbackAbort

    if pre_callback is not None:
        try:
            exec compile(pre_callback, '<rez pre-callback>', 'exec') in \
                callback_globals
        except CallbackAbort as e:
            print >> sys.stderr, "rez: command aborted by pre-callback: %s" \
                                 % e
            sys.exit(e.returncode)

    if post_callback is not None:
        def do_post_callback(returncode, error):
            callback_globals['returncode'] = returncode
            callback_globals['error'] = error
            try:
                exec compile(post_callback, '<rez post-callback>', 'exec') \
                    in callback_globals
            except CallbackAbort as e:
                print >> sys.stderr, "rez: returncode changed to %s by " \
                                     "post-callback: %s" % (e.returncode,
                                                            e)
                sys.exit(e.returncode)
    else:
        def do_post_callback(returncode, error):
            pass

    def run_cmd():
        try:
            returncode = opts.func(opts, opts.parser, arg_groups[1:])
        except Exception as e:
            do_post_callback(None, e)
            raise
        except SystemExit as e:
            do_post_callback(e.code, None)
            raise
        else:
            do_post_callback(returncode, None)
        return returncode

    if opts.profile:
        import cProfile
        cProfile.runctx("run_cmd()", globals(), locals(), filename=opts.profile)
        returncode = 0
    else:
        try:
            returncode = run_cmd()
        except (NotImplementedError, RezSystemError) as e:
            import traceback
            raise Exception(traceback.format_exc())
        except exc_type as e:
            print >> sys.stderr, "rez: %s: %s" % (e.__class__.__name__, str(e))
            sys.exit(1)



    sys.exit(returncode or 0)


if __name__ == '__main__':
    run()
