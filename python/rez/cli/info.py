'''
Print vital information about a package.
'''

import sys
import os.path
from rez.cli import error, output

##########################################################################################
# parse arguments
##########################################################################################

def setup_parser(parser):
#     usage = "usage: rez-info package"
#     p = optparse.OptionParser(usage=usage)
    parser.add_argument("pkg", metavar='PACKAGE', help="package name")

# if (len(sys.argv) == 1):
#     (opts, args) = p.parse_args(["-h"])
#     sys.exit(0)
#
# (opts, args) = p.parse_args()
#
# if len(args) == 1:
#     pkg = args[0]
# else:
#     p.error("incorrect number of arguments")


##########################################################################################
# find pkg and load metadata
##########################################################################################

def command(opts):
    from rez.packages import split_name, package_in_range
    import rez.sigint
    from rez.rez_util import get_epoch_time
    from rez.resources import load_metadata

    # attempt to load the latest
    pkg = package_in_range(*split_name(opts.pkg))

    output()
    output("info @ " + pkg.base + ":")

    if not pkg.metadata:
        error("The package appears to be missing a package.yaml.")
        sys.exit(1)

    infofile = os.path.join(pkg.base, ".metadata", "info.txt")
    pkg_info = load_metadata(infofile, force_config_version=0)

    output()

    if "description" in pkg.metadata:
        output("Description:")
        output(str(pkg.metadata["description"]).strip())
        output()

    if "authors" in pkg.metadata:
        output("Authors:")
        for auth in pkg.metadata["authors"]:
            output(auth)
        output()

    if pkg_info:
        output("REPOSITORY URL:")
        output(pkg_info['SVN'])
        output()

        release_date_secs = int(pkg_info['ACTUAL_BUILD_TIME'])
        now_secs = get_epoch_time()
        days = (now_secs - release_date_secs) / (3600 * 24)

        output("Days since last release:")
        output(days)

    output()































#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
