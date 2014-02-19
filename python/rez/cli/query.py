"""
An internal utility script for querying package.yaml files.
"""

import sys

from rez.resources import load_metadata
from rez.cli import output, error

def setup_parser(parser):

    parser.add_argument("-f", "--filepath", dest="filepath", type=str, required=True,
                        help="Path to the package file to be read.")
    parser.add_argument("-c", "--no_catch", dest="no_catch",
                        action="store_true", default=False,
                        help="Raise an exception if unable to read the package.yaml file.")
    parser.add_argument("-q", "--quiet", dest="quiet",
                        action="store_true", default=False,
                        help="Quiet mode, do not print errors.")
    parser.add_argument("-v", "--print-version", "--version", dest="print_version",
                        action="store_true", default=False,
                        help="Print the version of the package.")
    parser.add_argument("-d", "--print-desc", "--desc", dest="print_desc",
                        action="store_true", default=False,
                        help="Print the description.")
    parser.add_argument("-n", "--print-name", "--name", dest="print_name",
                        action="store_true", default=False,
                        help="Print the name of the package.")
    parser.add_argument("-b", "--print-build-requires", "--build-requires", dest="print_build_requires",
                        action="store_true", default=False,
                        help="Print the list of build requirements.")
    parser.add_argument("-r", "--print-requires", "--requires", dest="print_requires",
                        action="store_true", default=False,
                        help="Print the list of required packages.")
    parser.add_argument("-e", "--print-help", "--help-links", dest="print_help",
                        action="store_true", default=False,
                        help="Print the help resources this package provides.")
    parser.add_argument("-t", "--print-tools", "--tools", dest="print_tools",
                        action="store_true", default=False,
                        help="Print information about the tools this package provides.")
    parser.add_argument("-a", "--variant-num", "--variant", dest="variant_num", type=int,
                        default=None, help="Print information for the given variant number.")
    parser.add_argument("-k", "--resource-key", dest="resource_key", type=str,
                        default='package.built', help="The resource parser to use when reading the package.")


def command(opts):

    if opts.no_catch:
        metadata = load_metadata(opts.filepath, resource_key=opts.resource_key)

    else:
        try:
                metadata = load_metadata(opts.filepath, resource_key=opts.resource_key)

        except Exception as e:
                if not opts.quiet:
                        sys.stderr.write("Malformed package.yaml: '" + opts.filepath + "'.\n")
                        error(str(e))

                sys.exit(1)

    if opts.print_version:
        if metadata['version']:
            output(str(metadata['version']))

        else:
            if not opts.quiet:
                error("No 'version' in " + opts.filepath + ".\n")
            sys.exit(1)

    if opts.print_desc:
        if metadata['description']:
            output(str(metadata['description']))

    if opts.print_name:
        if metadata['name']:
            bad_chars = [ '-', '.' ]

            for ch in bad_chars:
                if (metadata['name'].find(ch) != -1):
                    error("Package name '" + metadata['name'] + "' contains illegal character '" + ch + "'.\n")
                    sys.exit(1)

            print output(str(metadata['name']))

        else:
            if not opts.quiet:
                error("No 'name' in " + opts.filepath + ".\n")

            sys.exit(1)

    if opts.print_build_requires:
        build_requires = metadata['build_requires']
        if build_requires:
            strs = str(' ').join(build_requires)
            output(strs)

    if opts.print_requires:
        requires = metadata['requires']
        if requires:
            strs = str(' ').join(requires)
            output(strs)

    if opts.print_help:
        if metadata['help']:
            output(str(metadata.help))

        else:
            if not opts.quiet:
                error("No 'help' entry specified in " + opts.filepath + ".\n")

            sys.exit(1)

    if opts.print_tools:
        tools = metadata['tools']
        if tools:
            output(str(' ').join(tools))

    if opts.variant_num != None:
        variants = metadata['variants']
        if variants:
            if (opts.variant_num >= len(variants)):
                if not opts.quiet:
                    error("Variant #" + str(opts.variant_num) + " does not exist in package.\n")

                sys.exit(1)

            else:
                strs = str(' ').join(variants[opts.variant_num])
                output(strs)

        else:
            if not opts.quiet:
                error("Variant #" + str(opts.variant_num) + " does not exist in package.\n")

            sys.exit(1)

#    Copyright 2012 BlackGinger Pty Ltd (Cape Town, South Africa)
#
#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either metadata.version 3 of the License, or
#    (at your option) any later metadata.version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
