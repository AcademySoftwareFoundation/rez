"""
Search for packages.
"""

import sys

def setup_parser(parser, completions=False):
    from rez.package_search import fields
    types_ = ("package", "family", "variant", "auto")

    parser.add_argument(
        "-s", "--sort", action="store_true",
        help="print results in sorted order")
    parser.add_argument(
        "-t", "--type", default="auto", choices=types_,
        help="type of resource to search for. If 'auto', either packages or "
        "package families are searched, depending on the value of PKG")
    parser.add_argument(
        "--nl", "--no-local", dest="no_local", action="store_true",
        help="don't search local packages")
    parser.add_argument(
        "--validate", action="store_true",
        help="validate each resource that is found")
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path")
    parser.add_argument(
        "-f", "--format", type=str, default=None,
        help="format package output, eg --format='{qualified_name} | "
        "{description}'. Valid fields include: %s" % ", ".join(fields))
    parser.add_argument(
        "--no-newlines", action="store_true",
        help="print newlines as '\\n' rather than actual newlines")
    parser.add_argument(
        "-l", "--latest", action="store_true",
        help="when searching packages, only show the latest version of each "
        "package")
    parser.add_argument(
        "-e", "--errors", action="store_true",
        help="search for packages containing errors")
    parser.add_argument(
        "--nw", "--no-warnings", dest="no_warnings", action="store_true",
        help="suppress warnings")
    parser.add_argument(
        "--before", type=str, default='0',
        help="only show packages released before the given time. Supported "
        "formats are: epoch time (eg 1393014494), or relative time (eg -10s, "
        "-5m, -0.5h, -10d)")
    parser.add_argument(
        "--after", type=str, default='0',
        help="only show packages released after the given time. Supported "
        "formats are: epoch time (eg 1393014494), or relative time (eg -10s, "
        "-5m, -0.5h, -10d)")
    PKG_action = parser.add_argument(
        "PKG", type=str, nargs='?',
        help="packages to search, glob-style patterns are supported")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.package_search import ResourceSearch, ResourceSearchResultFormatter, ResourceSearchResultPrinter
    from rez.utils.formatting import get_epoch_time_from_str
    from rez.config import config

    before_time = get_epoch_time_from_str(opts.before)
    after_time = get_epoch_time_from_str(opts.after)
    if after_time and before_time and (after_time >= before_time):
        parser.error("non-overlapping --before and --after")

    if opts.no_warnings:
        config.override("warn_none", True)

    resource_searcher = ResourceSearch(opts.PKG,
                                       package_paths=opts.paths,
                                       resource_type=opts.type,
                                       no_local=opts.no_local,
                                       latest=opts.latest,
                                       after_time=opts.after,
                                       before_time=opts.before,
                                       validate=opts.validate,
                                       sort_results=opts.sort,
                                       search_for_errors=opts.errors,
                                       debug=opts.debug)

    search_results = resource_searcher.search()
    resource_printer = ResourceSearchResultPrinter()

    if search_results:
        resource_formatter = ResourceSearchResultFormatter(opts.format, opts.no_newlines, opts.debug)
        formatted_search_results = resource_formatter.format_search_results(search_results)
        resource_printer.print_formatted_search_results(formatted_search_results)
    else:
        if opts.errors:
            resource_printer.print_formatted_search_result("no erroneous packages found")
        else:
            resource_printer.print_formatted_search_result("no matches found")
            sys.exit(-1)


