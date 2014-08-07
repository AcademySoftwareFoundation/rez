'''
Manage a suite or print information about an existing suite.
'''
import os.path


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-t", "--print-tools", dest="print_tools", action="store_true",
        help="print a list of the executables available in the suite")
    parser.add_argument(
        "--validate", action="store_true",
        help="validate the suite")
    parser.add_argument(
        "--create", action="store_true",
        help="create an empty suite at DIR")
    parser.add_argument(
        "-c", "--context", type=str, metavar="NAME",
        help="specify a context name (only used when using a context-specific "
        "option, such as --add)")
    parser.add_argument(
        "-i", "--interactive", action="store_true",
        help="enter an interactive shell in the given context")
    add_action = parser.add_argument(
        "-a", "--add", type=str, metavar="RXT",
        help="add a context to the suite")
    parser.add_argument(
        "-r", "--remove", type=str, metavar="NAME",
        help="remove a context from the suite")
    parser.add_argument(
        "-d", "--description", type=str, metavar="DESC",
        help="set the description of a context in the suite")
    parser.add_argument(
        "-p", "--prefix", type=str,
        help="set the prefix of a context in the suite")
    parser.add_argument(
        "-s", "--suffix", type=str,
        help="set the suffix of a context in the suite")
    parser.add_argument(
        "--hide", type=str, metavar="TOOL",
        help="hide a tool of a context in the suite")
    parser.add_argument(
        "--unhide", type=str, metavar="TOOL",
        help="unhide a tool of a context in the suite")
    parser.add_argument(
        "--alias", type=str, nargs=2, metavar=("TOOL", "ALIAS"),
        help="create an alias for a tool in the suite")
    parser.add_argument(
        "--unalias", type=str, metavar="TOOL",
        help="remove an alias for a tool in the suite")
    parser.add_argument(
        "-b", "--bump", type=str, metavar="NAME",
        help="bump a context, making its tools higher priority than others")
    DIR_action = parser.add_argument(
        "DIR", type=str, nargs='?',
        help="directory of suite to create or manage")

    if completions:
        from rez.cli._complete_util import FilesCompleter
        DIR_action.completer = FilesCompleter(dirs=True, files=False)
        add_action.completer = FilesCompleter(dirs=False, file_patterns=["*.rxt"])


def argname(attr):
    return "--%s" % attr.replace('_', '-')


def command(opts, parser, extra_arg_groups=None):
    from rez.status import status
    from rez.suite import Suite
    from rez.exceptions import SuiteError
    from rez.resolved_context import ResolvedContext
    from rez.colorize import Printer, heading
    import sys

    # validate args
    suite_actions = dict(create=[],
                         remove=[],
                         bump=[],
                         add=["context"],
                         description=["context"],
                         prefix=["context"],
                         suffix=["context"],
                         hide=["context"],
                         unhide=["context"],
                         alias=["context"],
                         unalias=["context"],
                         interactive=["context"])

    query_only = True
    for act, requires in suite_actions.iteritems():
        if getattr(opts, act, None):
            query_only = False
            option = argname(act)
            if not opts.DIR:
                parser.error("DIR must be supplied when using %s" % option)
            if not all(getattr(opts, x, None) for x in requires):
                parser.error("%s must be supplied when using %s"
                             % (argname(requires[0]), option))

    # interactive operations
    if opts.interactive:
        suite = Suite.load(opts.DIR)
        context = suite.context(opts.context)
        retcode, _, _ = context.execute_shell(block=True)
        sys.exit(retcode)

    # read-only operations
    if query_only:
        _pr = Printer()
        if opts.DIR:
            suite = Suite.load(opts.DIR)
            suites = [suite]
        else:
            suites = status.suites

        if opts.validate:
            if not opts.DIR:
                parser.error("DIR must be supplied when using --validate")
            try:
                suite.validate()
            except SuiteError as e:
                print >> sys.stderr, "The suite is invalid:\n%s" % str(e)
                sys.exit(1)
            print "The suite is valid."
        elif opts.print_tools:
            for i, suite in enumerate(suites):
                if not opts.DIR:
                    if i:
                        _pr()
                    _pr("suite: %s" % suite.load_path, heading)
                    _pr()
                suite.print_tools(verbose=opts.verbose)
        elif opts.DIR:
            suite.print_info(verbosity=opts.verbose)
        elif not status.print_suite_info(verbosity=opts.verbose):
            sys.exit(1)
        sys.exit(0)

    # operations that alter the suite
    def _pr(s):
        if opts.verbose:
            print s

    if opts.create:
        suite = Suite()
        _pr("create empty suite at %r..." % opts.DIR)
        suite.save(opts.DIR)  # raises if dir already exists
    else:
        _pr("loading suite at %r..." % opts.DIR)
        suite = Suite.load(opts.DIR)

        if opts.add:
            _pr("loading context at %r..." % opts.add)
            context = ResolvedContext.load(opts.add)
            _pr("adding context %r..." % opts.context)
            suite.add_context(name=opts.context,
                              context=context,
                              description=opts.description)
        elif opts.remove:
            _pr("removing context %r..." % opts.context)
            suite.remove_context(name=opts.remove)
        elif opts.bump:
            _pr("bumping context %r..." % opts.context)
            suite.bump_context(name=opts.bump)
        elif opts.description:
            _pr("setting description on context %r..." % opts.context)
            suite.set_context_description(name=opts.context,
                                          description=opts.description)
        elif opts.prefix or opts.suffix:
            if opts.prefix:
                _pr("prefixing context %r..." % opts.context)
                suite.set_context_prefix(name=opts.context,
                                         prefix=opts.prefix)
            if opts.suffix:
                _pr("suffixing context %r..." % opts.context)
                suite.set_context_suffix(name=opts.context,
                                         suffix=opts.suffix)
        elif opts.hide:
            _pr("hiding tool %r in context %r..."
                % (opts.hide, opts.context))
            suite.hide_tool(context_name=opts.context,
                            tool_name=opts.hide)
        elif opts.unhide:
            _pr("unhiding tool %r in context %r..."
                % (opts.unhide, opts.context))
            suite.unhide_tool(context_name=opts.context,
                              tool_name=opts.unhide)
        elif opts.alias:
            _pr("aliasing tool %r as %r in context %r..."
                % (opts.alias[0], opts.alias[1], opts.context))
            suite.alias_tool(context_name=opts.context,
                             tool_name=opts.alias[0],
                             tool_alias=opts.alias[1])
        elif opts.unalias:
            _pr("unaliasing tool %r in context %r..."
                % (opts.unalias, opts.context))
            suite.unalias_tool(context_name=opts.context,
                               tool_name=opts.unalias)

        _pr("saving suite to %r..." % opts.DIR)
        suite.save(opts.DIR)
