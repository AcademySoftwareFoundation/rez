'''
Provide general help about rez.
'''

import os
import os.path
import sys
import subprocess
import rez.sigint

suppress_notfound_err = False

def get_help(pkg):
    import yaml
    import rez.rez_config as dc
    global suppress_notfound_err

    try:
        pkg_base_path = dc.get_base_path(pkg)
    except Exception:
        if not suppress_notfound_err:
            sys.stderr.write("Package not found: '" + pkg + "'\n")
        sys.exit(1)

    yaml_file = pkg_base_path + "/package.yaml"
    try:
        metadict = yaml.load(open(yaml_file).read())
    except Exception:
        return (pkg_base_path, pkg_base_path, None)

    pkg_path = pkg_base_path
    if "variants" in metadict:
        # just pick first variant, they should all have the same copy of docs...
        v0 = metadict["variants"][0]
        pkg_path = os.path.join(pkg_path, *v0)

    return (pkg_base_path, pkg_path, metadict.get("help"), metadict.get("description"))


##########################################################################################
# parse arguments
##########################################################################################
def setup_parser(parser):
    parser.add_argument("pkg", metavar='PACKAGE',
                        help="package name")
    parser.add_argument("section", type=int, metavar='SECTION', default=0, nargs='?')
    parser.add_argument("-m", "--manual", dest="manual", action="store_true",
                        default=False,
                        help="Load the rez technical user manual")
    parser.add_argument("-e", "--entries", dest="entries", action="store_true",
                        default=False,
                        help="Just print each help entry")

# if (len(sys.argv) == 1):
#     (opts, args) = p.parse_args(["-h"])
#     sys.exit(0)
#
# (opts, args) = p.parse_args()

def command(opts):
    if opts.manual:
        subprocess.Popen("kpdf " + os.environ["REZ_PATH"] + "/docs/technicalUserManual.pdf &",
                         shell=True).communicate()
        sys.exit(0)

    pkg = opts.pkg
    section = opts.section
#     section = 0
#
#     if len(args) == 1:
#         pkg = args[0]
#     elif len(args) == 2:
#         pkg = args[1]
#         try:
#             section = int(args[0])
#         except Exception:
#             pass
#         if section < 1:
#             p.error("invalid section '" + args[0] + "': must be a number >= 1")
#     else:
#         p.error("incorrect number of arguments")

    ##########################################################################################
    # find pkg and load help metadata
    ##########################################################################################
    descr_printed = False

    def _print_descr(descr):
        global descr_printed
        if descr and not descr_printed:
            print
            print "Description:"
            print descr.strip()
            print
            descr_printed = True

    # attempt to load the latest
    fam = pkg.split("=")[0].split("-", 1)[0]
    base_pkgpath, pkgpath, help, descr = get_help(pkg)
    _print_descr(descr)
    suppress_notfound_err = True

    while not help:
        sys.stderr.write("Help not found in " + pkgpath + '\n')
        ver = pkgpath.rsplit('/')[-1]
        base_pkgpath, pkgpath, help, descr = get_help(fam + "-0+<" + ver)
        _print_descr(descr)

    print "help found for " + pkgpath

    ##########################################################################################
    # determine help command
    ##########################################################################################
    cmds = []

    if isinstance(help, type('')):
        cmds.append(["", help])
    elif isinstance(help, type([])):
        for entry in help:
            if (isinstance(entry, type([]))) and (len(entry) == 2) \
                    and (isinstance(entry[0], type(''))) and (isinstance(entry[1], type(''))):
                cmds.append(entry)

    if len(cmds) == 0:
        print "Malformed help info in '" + yaml_file + "'"
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
    cmd = cmds[section - 1][1]
    cmd = cmd.replace('!ROOT!', pkgpath)
    cmd = cmd.replace('!BASE!', base_pkgpath)
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
