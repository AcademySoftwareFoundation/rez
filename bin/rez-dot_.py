#!!REZ_PYTHON_BINARY!

#
# Thin wrapper over pydot, so dot-files can be displayed from the command line
#

import os
import sys
import optparse
import pydot
import subprocess
import tempfile


#########################################################################################
# command-line
#########################################################################################

usage = "usage: %prog [options] dot-file"
p = optparse.OptionParser(usage=usage)

default_viewer = os.getenv("REZ_DOT_IMAGE_VIEWER", "xnview")

p.add_option("-v", "--viewer", dest="viewer", type="string", default=default_viewer, \
	help="app to view image with [default = "+default_viewer+"]")
p.add_option("-q", "--quiet", dest="quiet", action="store_true", default=False, \
	help="suppress unnecessary output [default = %default]")
p.add_option("-c", "--conflict-only", dest="conflict_only", action="store_true", default=False, \
	help="only display nodes associated with a conflict [default = %default]")
p.add_option("-p", "--package", dest="package", type="string", default="", \
	help="only display nodes dependent (directly or indirectly) on the given package.")
p.add_option("-r", "--ratio", dest="ratio", type="float", default=-1, \
	help="image height / image width")
p.add_option("-f", "--filename", dest="filename", type="string", \
	help="write out the image to file and exit (won't delete it)")

if (len(sys.argv) == 1):
	(opts, extraArgs) = p.parse_args(["-h"])
	sys.exit(0)

(opts, dotfile) = p.parse_args()
if len(dotfile) != 1:
	p.error("Expected a single dot-file")
dotfile = dotfile[0]


if not os.path.isfile(dotfile):
	sys.stderr.write("File does not exist.\n")
	sys.exit(1)


#########################################################################################
# strip out all nodes not associated with a conflict / associated with a particular pkg
#########################################################################################

g = None

if (opts.conflict_only) or (opts.package != ""):

	oldg = pydot.graph_from_dot_file(dotfile)

	# group graph edges by dest pkg, and find 'seed' pkg(s)
	edges = {}
	seed_pkgs = set()
	opt_pkg_exists_as_source = False

	oldedges = oldg.get_edge_list()
	for e in oldedges:
		pkgsrc = e.get_source().replace('"','')
		pkgdest = e.get_destination()

		if pkgdest in edges:
			edges[pkgdest].add(e)
		else:
			s = set()
			s.add(e)
			edges[pkgdest] = s

		if opts.conflict_only and \
			"label" in e.get_attributes() and \
			e.get_attributes()["label"] == "CONFLICT":
			seed_pkgs.add(pkgdest)
		elif opts.package != "":
			pkgdest_ = pkgdest.replace('"','')
			if pkgdest_.startswith(opts.package):
				seed_pkgs.add(pkgdest)
			if pkgsrc.startswith(opts.package):
				opt_pkg_exists_as_source = True

	# extract all edges dependent (directly or not) on seed pkgs
	newg = pydot.Dot()
	consumed_edges = set()

	if len(seed_pkgs) > 0:
		while True:
			new_seed_pkgs = set()
			for seed_pkg in seed_pkgs:
				seed_edges = edges.get(seed_pkg)
				if seed_edges:
					for seededge in seed_edges:
						attribs = seededge.get_attributes()
						if "lp" in attribs:
							del attribs["lp"]
						if "pos" in attribs:
							del attribs["pos"]

						if seededge not in consumed_edges:
							newg.add_edge(seededge)
							consumed_edges.add(seededge)
						new_seed_pkgs.add(seededge.get_source())

			if len(new_seed_pkgs) == 0:
				break
			seed_pkgs = new_seed_pkgs

	if len(newg.get_edge_list()) > 0:
		g = newg
	elif opt_pkg_exists_as_source:
		# pkg was directly in the request list
		e = pydot.Edge("DIRECT REQUEST", opts.package)
		newg.add_edge(e)
		g = newg


#########################################################################################
# generate dot image
#########################################################################################

if opts.filename:
	imgfile = opts.filename
else:
	tmpf = tempfile.mkstemp(suffix='.jpg')
	os.close(tmpf[0])
	imgfile = tmpf[1]

if not opts.quiet:
	print "reading dot file..."
	sys.stdout.flush()

if not g:
	g = pydot.graph_from_dot_file(dotfile)


if opts.ratio > 0:
	g.set_ratio(str(opts.ratio))

if not opts.quiet:
	print "rendering image to " + imgfile + "..."
	sys.stdout.flush()

g.write_jpg(imgfile)


#########################################################################################
# view it then delete it or just exit if we're saving to a file
#########################################################################################

if not opts.filename:
	if not opts.quiet:
		print "loading viewer..."
	proc = subprocess.Popen(opts.viewer + " " + imgfile, shell=True)
	proc.wait()

	if proc.returncode != 0:
		subprocess.Popen("firefox " + imgfile, shell=True).wait()

	os.remove(imgfile)











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
