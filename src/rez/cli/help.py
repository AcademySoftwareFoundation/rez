"""
Utility for displaying help for the given package. This is determined via the
'help' entry in the package.yaml, if that entry does not exist then an error
results.
"""
from rez.vendor.version.requirement import Requirement
from rez.package_help import PackageHelp
import sys


def setup_parser(parser, completions=False):
    parser.add_argument("-m", "--manual", dest="manual", action="store_true",
                        default=False,
                        help="Load the rez technical user manual")
    parser.add_argument("-e", "--entries", dest="entries", action="store_true",
                        default=False,
                        help="Just print each help entry")
    PKG_action = parser.add_argument(
        "PKG", metavar='PACKAGE', nargs='?',
        help="package name")
    parser.add_argument("SECTION", type=int, default=1, nargs='?',
                        help="Help section to view (1..N)")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG_action.completer = PackageCompleter


def command(opts, parser=None, extra_arg_groups=None):
    if opts.manual or not opts.PKG:
        PackageHelp.open_rez_manual()
        sys.exit(0)

    request = Requirement(opts.PKG)
    if request.conflict:
        raise ValueError("Expected a non-conflicting package")

    help_ = PackageHelp(request.name, request.range, verbose=opts.verbose)
    if not help_.success:
        print >> sys.stderr, ("Could not find a package with help for %s."
                              % requirement)
        sys.exit(1)

    package = help_.package
    print "Help found for:"
    print package.path
    if package.description:
        print
        print "Description:"
        print package.description.strip()
        print

    if opts.entries:
        help_.print_info()
    else:
        try:
            help_.open(opts.SECTION - 1)
        except IndexError:
            print >> sys.stderr, "No such help section."
            sys.exit(2)
