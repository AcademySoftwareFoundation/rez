#!!REZ_PYTHON_BINARY!

#
# Display unversioned dependency information of every package found in the given directory,
# or the default central packages directory if none is specified. Only information from the
# latest version of every package is used.
#
# examples:
#
# to print a list of packages that directly or indirectly use vacuum:
# rez-depends vacuum
#
# to print a list of packages that directly use vacuum:
# rez-depends --depth=1 vacuum
#
# to check for cyclic dependencies over all packages:
# rez-depends --cyclic-test-only
#
# to view a dot-graph showing all dependencies of boost:
# rez-depends --show-dot boost
#
# to view a dot-graph showing all dependencies of all packages (a BIG image):
# rez-depends --show-dot --all
#


import os
import os.path
import sys
import optparse
import yaml
import sigint

import filesys as fs


#########################################################################################
# functions
#########################################################################################

def _detect_cycle(pkgmap, depchain, depset):
	pkg = depchain[-1]
	if pkg in pkgmap:
		for pkg2 in pkgmap[pkg]:
			if pkg2 in depset:
				depchain2 = depchain[:]
				while depchain2[0] != pkg2:
					del depchain2[0]
				depchain2.append(pkg2)
				return depchain2

			depchain2 = depchain[:]
			depset2 = depset.copy()
			depchain2.append(pkg2)
			depset2.add(pkg2)
			depchain3 = _detect_cycle(pkgmap, depchain2, depset2)
			if len(depchain3) > 0:
				return depchain3

	return []


def detect_cycle(pkg, pkgmap):
	return _detect_cycle(pkgmap, [pkg], set(pkg))



#########################################################################################
# command-line
#########################################################################################

usage = "usage: %prog [options] pkg1 pkg2 ... pkgN"
p = optparse.OptionParser(usage=usage)

p.add_option("-p", "--path", dest="path", default=os.environ["REZ_PACKAGES_PATH"], \
	help="path where packages are located [default = %default]")
p.add_option("-d", "--depth", dest="depth", type="int", default=0, \
	help="max recursion depth, defaults to no limit (0)")
p.add_option("-q", "--quiet", dest="quiet", action="store_true", default=False, \
	help="suppress unnecessary output [default = %default]")
p.add_option("-a", "--all", dest="all", action="store_true", default=False, \
	help="select all existing packages (pkg1 .. pkgN will be ignored) [default = %default]")
p.add_option("--cyclic-test-only", dest="ctest", action="store_true", default=False, \
	help="just perform cyclic dependency checks, then exit [default = %default]")
p.add_option("--print-dot", dest="printdot", action="store_true", default=False, \
	help="print dependency info in dot notation [default = %default]")
p.add_option("--show-dot", dest="showdot", action="store_true", default=False, \
	help="display dependency info in a dot graph [default = %default]")


if (len(sys.argv) == 1):
	p.parse_args(["-h"])
	sys.exit(0)

(opts, packages) = p.parse_args()
packages_set = set(packages)


if not os.path.isdir(opts.path):
	sys.stderr.write("'" + opts.path + "' is not a directory.\n")
	sys.exit(1)

if opts.depth == 0:
	opts.depth = -1


#########################################################################################
# main
#########################################################################################

#----------------------------------------------------------------------------------------
# create a map of package dependency info
#----------------------------------------------------------------------------------------

dependsMap = {}

all_packages = set()
all_dirs = os.listdir(opts.path)

if not opts.quiet:
	print("gathering packages...")
	sys.stdout.write('[           ]\b\b\b\b\b\b\b\b\b\b\b\b.')
	sys.stdout.flush()
	progstep = len(all_dirs) / 10.0
	ndir = 0

for f in all_dirs:

	if not opts.quiet:
		prog1 = ndir / progstep
		ndir = ndir + 1
		prog2 = ndir / progstep
		if int(prog1) < int(prog2):
			sys.stdout.write('.')
			sys.stdout.flush()

	# tmp until rez is bootstrapped with itself
	if (f == "rez"):
		continue

	all_packages.add(f)

	fullpath = os.path.join(opts.path, f)
	if os.path.isdir(fullpath):
		vers = fs.get_versions_in_directory(fullpath, False, 0, False)
		if vers and (len(vers) > 0):
			filename = fullpath + '/' + str(vers[0]) + "/package.yaml"
			metadict = yaml.load(open(filename).read())

			reqs = metadict["requires"] if ("requires" in metadict) else []
			vars = metadict["variants"] if ("variants" in metadict) else []
			if len(reqs) + len(vars) > 0:

				fn_unver = lambda pkg: pkg.split('-')[0]
				deps = set(map(fn_unver, reqs))
				for var in vars:
					deps = deps | set(map(fn_unver, var))

				for dep in deps:
					if dep not in dependsMap:
						dependsMap[dep] = set()
					dependsMap[dep].add(f)


if not opts.quiet:
	print("\ndetecting cyclic dependencies...")

if opts.all:
	packages_set = all_packages


#----------------------------------------------------------------------------------------
# detect cyclic dependencies. Note that this has to be done over all packages, since we
# can't know ahead of time what packages will end up in the dependency tree
#----------------------------------------------------------------------------------------

cycles = set()
cycle_pkgs = set()

for pkg in all_packages:
	cycle = detect_cycle(pkg, dependsMap)
	if len(cycle) > 0:

		# A<--B<--A is the same as B<--A<--B so rotate the list until the smallest string
		# is at the front, so we don't get multiple reports of the same cycle
		del cycle[-1]
		smallest_str = cycle[0]
		for cpkg in cycle:
			if cpkg < smallest_str:
				smallest_str = cpkg
		while cycle[0] != smallest_str:
			cycle.append(cycle[0])
			del cycle[0]

		cycle_pkgs |= set(cycle)
		cycle.append(cycle[0])
		cycle_str = str("<--").join(cycle)
		cycles.add(cycle_str)

if len(cycles) > 0:
		if not opts.quiet:
			print("CYCLIC DEPENDENCY(S) DETECTED; ALL INVOLVED PACKAGES WILL BE REMOVED FROM FURTHER PROCESSING:")
			for c in cycles:
				print c

		if opts.ctest:
			sys.exit(1)

		if not opts.quiet:
			print

		for cpkg in cycle_pkgs:
			if cpkg in dependsMap:
				del dependsMap[cpkg]

		for dpkg in dependsMap:
			dependsMap[dpkg] -= cycle_pkgs


if opts.ctest:
	sys.exit(0)



#----------------------------------------------------------------------------------------
# find pkgs dependent on the given pkgs
#----------------------------------------------------------------------------------------

if not opts.quiet:
	print("identifying dependencies...")

deps = packages_set
deps2 = set()
depsAll = set()
depth = 0

dotout = None
if opts.printdot:
	dotout = sys.stdout
elif opts.showdot:
	import cStringIO
	dotout = cStringIO.StringIO()

if dotout:
	from rez_config import make_random_color_string
	dotout.write("digraph g { \n")
	dotpairs = set()

while (len(deps) > 0) and (depth != opts.depth):
	if not opts.quiet:
		print "@ depth " + str(depth) + " (" + str(len(deps)) + " packages)..."

	for dep in deps:
		if dep in dependsMap:
			mapentry = dependsMap[dep]
			deps2 |= mapentry
			depsAll |= mapentry
			del dependsMap[dep]

			if dotout:
				for pkg in mapentry:
					dotpair_str = pkg + " -> " + dep
					if dotpair_str not in dotpairs:
						rcol = make_random_color_string()
						dotout.write('    ' + dotpair_str + ' [color="' + rcol + '"];\n')
						dotpairs.add(dotpair_str)

	deps = deps2
	deps2 = set()
	depth = depth + 1

if dotout:
	dotout.write("} \n")
	dotout.flush()

	if opts.showdot:
		import pydot
		import tempfile

		g = pydot.graph_from_dot_data(dotout.getvalue())
		dotout.close()
		fd, jpgpath = tempfile.mkstemp('.jpg')
		os.close(fd)
		g.write_jpg(jpgpath)

		import subprocess
		cmd = os.getenv("REZ_DOT_IMAGE_VIEWER", "xnview") + " " + jpgpath
		if not opts.quiet:
			print("invoking: " + cmd)
		pret = subprocess.Popen(cmd, shell=True)
		pret.communicate()
		os.remove(jpgpath)


# print dependent packages
if not dotout:
	for dep in depsAll:
		print dep
















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
