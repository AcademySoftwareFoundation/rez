"""
Prints information about a rez package
"""
import os
import sys
from rez.vendor import argparse
from rez.utils.sourcecode import SourceCode

def setup_parser(parser, completions=False):
    parser.add_argument(
        "-p", "--path", type=str, default=os.getcwd(),
        help="Path to the rez package. Defaults to the current working directory")
    parser.add_argument(
        "-s", "--separator", type=str, default=" ",
        help="Separator to be used when printing lists. defaults to empty space ")
    parser.add_argument(
        "-r", "--raw", dest="raw", action="store_true",
        help="Prints the fields as they come from the package dictionary, by default it tries to pretty print them")

    parser.add_argument(
        "INFO_ARGS", metavar="ARG", nargs=argparse.REMAINDER,
        help="Space separated list of package field names. ie. version name requires")

def command(opts, parser, extra_arg_groups=None):
    from rez.packages_ import get_developer_package
    from rez.exceptions import PackageMetadataError

    if not os.path.exists(opts.path):
        print "The path %s does not exist" % opts.path
        sys.exit(-1)
    try:
        package = get_developer_package(opts.path)
    except PackageMetadataError:
        print "There is no rez package at %s " % opts.path
        print "Run this command from the root of a rez package or pass the path to a rez package using -p"
        sys.exit(-1)

    info = get_package_info(package, opts.INFO_ARGS, opts.separator, opts.raw)
    print info


def get_package_info(package, args, separator, raw):
    package_dict = package.data
    package_info = ''
    for field in args:
        if not package_dict.has_key(field):
            print "Package does not have a field called:", field
            continue
        if raw:
            package_info = "%s%s\n" % (package_info, package_dict[field])
        else:
            package_info = "%s%s\n" % (package_info, format_string(package_dict[field], separator))

    return package_info.rstrip('\n')


def format_string(field, separator):
    """
    format lists and nested lists in a more convenient way to be used in scripts
    """
    if isinstance(field, str) or isinstance(field, SourceCode):
        return field
    if isinstance(field, list):
        listToString = ''
        for f in field:
            if isinstance(f, list):
                listToString = "%s%s\n" % (listToString, format_string(f, separator))
            else:
                listToString += "%s%s" % (f, separator)
        if listToString:
            if listToString.endswith(separator):
                return listToString[:-len(separator)]
            else:
                return listToString
