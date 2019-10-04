'''
Manage a suite or print information about an existing suite.
'''
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-l", "--list", action="store_true",
        help="list visible suites")
    parser.add_argument(
        "-t", "--tools", dest="print_tools", action="store_true",
        help="print a list of the executables available in the suite")
    parser.add_argument(
        "--which", type=str, metavar="TOOL",
        help="print path to the tool in the suite, if it exists")
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
    add_action = parser.add_argument(
        "-P", "--prefix-char", dest="prefix_char", type=str, metavar="CHAR",
        help="set the char used to access rez options via a suite tool "
        "for the context being added (default: '+'). If set to the empty string, "
        "rez options are disabled. This option is only used in combination with "
        "--add")
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
    find_request_action = parser.add_argument(
        "--find-request", type=str, metavar="PKG",
        help="find the contexts that contain the given package in the request")
    find_resolve_action = parser.add_argument(
        "--find-resolve", type=str, metavar="PKG",
        help="find the contexts that contain the given package in the resolve")
    DIR_action = parser.add_argument(
        "DIR", type=str, nargs='?',
        help="directory of suite to create or manage")

    if completions:
        from rez.cli._complete_util import FilesCompleter, PackageCompleter, \
            PackageFamilyCompleter
        DIR_action.completer = FilesCompleter(dirs=True, files=False)
        add_action.completer = FilesCompleter(dirs=False, file_patterns=["*.rxt"])
        find_request_action.completer = PackageFamilyCompleter
        find_resolve_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.suite import Suite
    from rez.status import status
    from rez.exceptions import SuiteError
    from rez.resolved_context import ResolvedContext
    import sys

    context_needed = set(("add", "prefix", "suffix", "hide", "unhide", "alias",
                          "unalias", "interactive"))
    save_needed = set(("add", "remove", "bump", "prefix", "suffix", "hide",
                       "unhide", "alias", "unalias"))

    def _pr(s):
        if opts.verbose:
            print(s)

    def _option(name):
        value = getattr(opts, name)
        if value and name in context_needed and not opts.context:
            parser.error("--context must be supplied when using --%s"
                         % name.replace('_', '-'))
        return value

    if opts.list:
        suites = status.suites
        if suites:
            for suite in suites:
                print(suite.load_path)
        else:
            print("No visible suites.")
        sys.exit(0)

    if not opts.DIR:
        parser.error("DIR required.")

    if opts.create:
        suite = Suite()
        _pr("create empty suite at %r..." % opts.DIR)
        suite.save(opts.DIR)  # raises if dir already exists
        sys.exit(0)

    suite = Suite.load(opts.DIR)

    if _option("interactive"):
        context = suite.context(opts.context)
        retcode, _, _ = context.execute_shell(block=True)
        sys.exit(retcode)
    elif _option("validate"):
        try:
            suite.validate()
        except SuiteError as e:
            print("The suite is invalid:\n%s" % str(e), file=sys.stderr)
            sys.exit(1)
        print("The suite is valid.")
    elif _option("find_request") or _option("find_resolve"):
        context_names = suite.find_contexts(in_request=opts.find_request,
                                            in_resolve=opts.find_resolve)
        if context_names:
            print('\n'.join(context_names))
    elif _option("print_tools"):
        suite.print_tools(verbose=opts.verbose, context_name=opts.context)
    elif _option("add"):
        _pr("loading context at %r..." % opts.add)
        context = ResolvedContext.load(opts.add)
        _pr("adding context %r..." % opts.context)
        suite.add_context(name=opts.context, context=context,
                          prefix_char=opts.prefix_char)
    elif _option("remove"):
        _pr("removing context %r..." % opts.remove)
        suite.remove_context(name=opts.remove)
    elif _option("bump"):
        _pr("bumping context %r..." % opts.bump)
        suite.bump_context(name=opts.bump)
    elif _option("prefix"):
        _pr("prefixing context %r..." % opts.context)
        suite.set_context_prefix(name=opts.context, prefix=opts.prefix)
    elif _option("suffix"):
        _pr("suffixing context %r..." % opts.context)
        suite.set_context_suffix(name=opts.context, suffix=opts.suffix)
    elif _option("hide"):
        _pr("hiding tool %r in context %r..." % (opts.hide, opts.context))
        suite.hide_tool(context_name=opts.context, tool_name=opts.hide)
    elif _option("unhide"):
        _pr("unhiding tool %r in context %r..." % (opts.unhide, opts.context))
        suite.unhide_tool(context_name=opts.context, tool_name=opts.unhide)
    elif _option("alias"):
        _pr("aliasing tool %r as %r in context %r..."
            % (opts.alias[0], opts.alias[1], opts.context))
        suite.alias_tool(context_name=opts.context,
                         tool_name=opts.alias[0],
                         tool_alias=opts.alias[1])
    elif _option("unalias"):
        _pr("unaliasing tool %r in context %r..." % (opts.unalias, opts.context))
        suite.unalias_tool(context_name=opts.context, tool_name=opts.unalias)
    elif _option("which"):
        filepath = suite.get_tool_filepath(opts.which)
        if filepath:
            print(filepath)
            sys.exit(0)
        else:
            sys.exit(1)
    elif opts.context:
        context = suite.context(opts.context)
        context.print_info(verbosity=opts.verbose)
    else:
        suite.print_info(verbose=opts.verbose)
        sys.exit(0)

    do_save = any(getattr(opts, x) for x in save_needed)
    if do_save:
        _pr("saving suite to %r..." % opts.DIR)
        suite.save(opts.DIR)


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
