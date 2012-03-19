#!!REZ_PYTHON_BINARY!

import sys
import yaml
import optparse
import subprocess
import rez_config as dc
import sigint

suppress_notfound_err = False

def get_help(pkg):

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
		return (pkg_base_path, None)

	if "help" not in metadict:
		return (pkg_base_path, None)

	return (pkg_base_path, metadict["help"])



##########################################################################################
# parse arguments
##########################################################################################

usage = "usage: rez-help [options] [section] package"
p = optparse.OptionParser(usage=usage)

p.add_option("-m", "--manual", dest="manual", action="store_true", default=False, \
	help="Load the rez technical user manual [default = %default]")
p.add_option("-e", "--entries", dest="entries", action="store_true", default=False, \
	help="Just print each help entry [default = %default]")

if (len(sys.argv) == 1):
	(opts, args) = p.parse_args(["-h"])
	sys.exit(0)

(opts, args) = p.parse_args()

if opts.manual:
	subprocess.Popen("kpdf "+os.environ["REZ_PATH"]+"/docs/technicalUserManual.pdf &", shell=True).communicate()
	sys.exit(0)

section = 0

if len(args) == 1:
	pkg = args[0]
elif len(args) == 2:
	pkg = args[1]
	try:
		section = int(args[0])
	except Exception:
		pass
	if section < 1:
		p.error("invalid section '" + args[0] + "': must be a number >= 1")
else:
	p.error("incorrect number of arguments")


##########################################################################################
# find pkg and load help metadata
##########################################################################################

# attempt to load the latest
fam = pkg.split("=")[0].split("-",1)[0]
pkgpath, help = get_help(pkg)
suppress_notfound_err = True

while not help:
	sys.stderr.write("Help not found in " + pkgpath + '\n')
	ver = pkgpath.rsplit('/')[-1]
	pkgpath, help = get_help(fam + "-0+<" + ver)

if not opts.entries:
	print "help found for " + pkgpath


##########################################################################################
# determine help command
##########################################################################################

cmds = []

if type(help) == type(''):
	cmds.append(["", help])
elif type(help) == type([]):
	for entry in help:
		if (type(entry) == type([])) and (len(entry) == 2) \
			and (type(entry[0]) == type('')) and (type(entry[1]) == type('')):
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

cmd = cmds[section-1][1]
cmd = cmd.replace('!ROOT!', pkgpath)
cmd = cmd.replace('!BASE!', pkgpath)
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
