'''
Provide general help about rez.
'''

import os
import os.path
import sys
import subprocess
import webbrowser
import rez.sigint
from rez.cli import error, output


suppress_notfound_err = False


def setup_parser(parser):
    parser.add_argument("pkg", metavar='PACKAGE',
                        help="package name", nargs='?')
    parser.add_argument("section", type=int, metavar='SECTION', default=0, nargs='?')
    parser.add_argument("-m", "--manual", dest="manual", action="store_true",
                        default=False,
                        help="Load the rez technical user manual")
    parser.add_argument("-e", "--entries", dest="entries", action="store_true",
                        default=False,
                        help="Just print each help entry")


def command(opts):
    if opts.manual or not opts.pkg:
        webbrowser.open("http://nerdvegas.github.io/rez/")
        sys.exit(0)

    pkg = opts.pkg
    section = opts.section

    ##########################################################################################
    # find pkg and load help metadata
    ##########################################################################################

    # attempt to load the latest
    from rez.packages import pkg_name, iter_packages_in_range
    name = pkg_name(opts.pkg)
    found_pkg = None
    for pkg in iter_packages_in_range(name):
        if pkg.metadata is None:
            continue
        if "help" in pkg.metadata:
            found_pkg = pkg
            break

    if found_pkg is None:
        error("Could not find a package with help for %s" % opts.pkg)
        sys.exit(1)

    help = pkg.metadata.get("help")
    descr = pkg.metadata.get("description")
    if descr:
        print
        print "Description:"
        print descr.strip()
        print

    print "help found for " + pkg.base

    ##########################################################################################
    # determine help command
    ##########################################################################################
    cmds = []

    if isinstance(help, basestring):
        cmds.append(["", help])
    elif isinstance(help, list):
        for entry in help:
            if (isinstance(entry, list)) and (len(entry) == 2) \
                    and (isinstance(entry[0], basestring)) and (isinstance(entry[1], basestring)):
                cmds.append(entry)

    if len(cmds) == 0:
        print "Malformed help info in '" + pkg.metafile + "'"
        sys.exit(1)

    if section > len(cmds):
        print "Help for " + pkg + " has no section " + str(section)
        section = 0

    if (len(cmds) == 1) and opts.entries:
        print "  1: help"
        sys.exit(0)

    if section == 0:
        section = 1
        if len(cmds) > 1:
            if not opts.entries:
                print "sections:"
            sec = 1
            for entry in help:
                print "  " + str(sec) + ":\t" + entry[0]
                sec += 1
            sys.exit(0)

    ##########################################################################################
    # run help command
    ##########################################################################################
    variants = pkg.metadata.get("variants")
    if variants:
        # just pick first variant, they should all have the same copy of docs...
        v0 = variants[0]
        pkg_path = os.path.join(pkg.base, *v0)
    else:
        pkg_path = pkg.base

    cmd = cmds[section - 1][1]
    cmd = cmd.replace('!ROOT!', pkg_path)
    cmd = cmd.replace('!BASE!', pkg.base)
    if len(cmd.split()) == 1:
        webbrowser.open(cmd)
    else:
        cmd += " &"
        subprocess.Popen(cmd, shell=True).communicate()




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
