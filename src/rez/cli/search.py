# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
Search for packages
"""
from __future__ import print_function

import os
import sys


def setup_parser(parser, completions=False):
    from rez.package_search import ResourceSearchResultFormatter

    type_choices = ("package", "family", "variant", "auto")
    format_choices = ", ".join(sorted(ResourceSearchResultFormatter.fields))

    parser.add_argument(
        "-t", "--type", default="auto", choices=type_choices,
        help="type of resource to search for. If 'auto', either packages or "
        "package families are searched, depending on the value of PKG")
    parser.add_argument(
        "--nl", "--no-local", dest="no_local", action="store_true",
        help="don't search local packages")
    parser.add_argument(
        "--validate", action="store_true",
        help="validate each resource that is found")
    parser.add_argument(
        "--paths", type=str,
        help="set package search path (ignores --no-local if set)")
    parser.add_argument(
        "-f", "--format", type=str,
        help="format package output, eg --format='{qualified_name} | "
        "{description}'. Valid fields include: %s" % format_choices)
    parser.add_argument(
        "--no-newlines", action="store_true",
        help="print newlines as '\\n' rather than actual newlines")
    parser.add_argument(
        "-l", "--latest", action="store_true",
        help="when searching packages, only show the latest version of each "
        "package")
    parser.add_argument(
        "-e", "--errors", action="store_true",
        help="only print packages containing errors (implies --validate)")
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
    parser.add_argument(
        "-s", "--sort", action="store_true",
        help="print results in sorted order (deprecated)")
    PKG_action = parser.add_argument(
        "PKG", type=str, nargs='?',
        help="packages to search, glob-style patterns are supported")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.package_search import ResourceSearcher, ResourceSearchResultFormatter
    from rez.utils.formatting import get_epoch_time_from_str
    from rez.config import config

    before_time = get_epoch_time_from_str(opts.before)
    after_time = get_epoch_time_from_str(opts.after)

    if after_time and before_time and (after_time >= before_time):
        parser.error("non-overlapping --before and --after")

    if opts.no_warnings:
        config.override("warn_none", True)

    if opts.paths:
        paths = opts.paths.split(os.pathsep)
        paths = [x for x in paths if x]
    else:
        paths = None

    if opts.type == "auto":
        type_ = None
    else:
        type_ = opts.type

    searcher = ResourceSearcher(
        package_paths=paths,
        resource_type=type_,
        no_local=opts.no_local,
        latest=opts.latest,
        after_time=after_time,
        before_time=before_time,
        validate=(opts.validate or opts.errors)
    )

    resource_type, search_results = searcher.search(opts.PKG)

    if opts.errors:
        search_results = [x for x in search_results if x.validation_error]

        if not search_results:
            print("No matching erroneous %s found." % resource_type, file=sys.stderr)
            sys.exit(1)

    elif not search_results:
        print("No matching %s found." % resource_type, file=sys.stderr)
        sys.exit(1)

    formatter = ResourceSearchResultFormatter(
        output_format=opts.format,
        suppress_newlines=opts.no_newlines
    )

    formatter.print_search_results(search_results)
