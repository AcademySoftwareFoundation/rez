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
    import yaml
    import rez.rez_config as dc
    import rez.sigint
    from rez.rez_util import get_epoch_time

    pkg = opts.pkg

    # attempt to load the latest
    try:
        pkg_base_path = dc.get_base_path(pkg)
    except Exception:
        error("Package not found: '" + pkg + "'")
        sys.exit(1)

    output()
    output("info @ " + pkg_base_path + ":")

    try:
        infofile = os.path.join(pkg_base_path + ".metadata", "info.txt")
        pkg_info = open(infofile).readlines()
    except Exception:
        pkg_info = None

    yaml_file = os.path.join(pkg_base_path, "package.yaml")

    if pkg_info:
        try:
            metadict = yaml.load(open(yaml_file).read())
        except Exception:
            error("The package appears to be missing a package.yaml.")
            sys.exit(1)

        output()

        if "description" in metadict:
            output("Description:")
            output(str(metadict["description"]).strip())
            output()

        if "authors" in metadict:
            output("Authors:")
            for auth in metadict["authors"]:
                output(auth)
            output()

        output("REPOSITORY URL:")
        svn_url = pkg_info[-1].split()[-1]
        output(svn_url)
        output()

        release_date_secs = int(pkg_info[0].split()[-1])
        now_secs = get_epoch_time()
        days = (now_secs - release_date_secs) / (3600 * 24)

        output("Days since last release:")
        output(days)
    else:
        try:
            metadict = yaml.load(open(yaml_file).read())
            output("The package appears to be external.")
            if "description" in metadict:
                output("Description:")
                output(str(metadict["description"]).strip())
                output()

        except Exception:
            output("The package was not released with rez-release.")

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
