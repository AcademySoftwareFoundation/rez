#!!REZ_PYTHON_BINARY!

#
# rez-config
#
# A tool for resolving a configuration request. Output from this util can be used to setup
# said configuration (rez-env does this).
#

import os
import sys
import optparse
import rez_config as dc
import filesys
import tempfile
import sigint


def gen_dotgraph_image(dot_data, out_file):
	import pydot
	graph = pydot.graph_from_dot_data(dot_data)

	# assume write format from image extension
	ext = "jpg"
	if(out_file.rfind('.') != -1):
		ext = out_file.split('.')[-1]

	try:
		fn = getattr(graph, "write_"+ext)
	except Exception:
		sys.stderr.write("could not write to '" + out_file + "': unknown format specified")
		sys.exit(1)

	fn(out_file)



##########################################################################################
# parse arguments
##########################################################################################

usage = "usage: %prog [options] pkg1 pkg2 ... pkgN"
p = optparse.OptionParser(usage=usage)

p.add_option("-m", "--mode", dest="mode", default="latest", \
	help="set resolution mode (earliest, latest) [default = %default]")
p.add_option("-v", "--verbosity", dest="verbosity", type="int", default=0, \
	help="set verbosity (0..2) [default = %default]")
p.add_option("--version", dest="version", action="store_true", default=False, \
	help="print the rez version number and exit [default = %default]")
p.add_option("--quiet", dest="quiet", action="store_true", default=False, \
	help="hide unnecessary output [default = %default]")
p.add_option("--no-os", dest="no_os", action="store_true", default=False, \
	help="stop rez from implicitly requesting the operating system package [default = %default]")
p.add_option("-b", "--build-requires", dest="buildreqs", action="store_true", default=False, \
	help="include build-only required packages [default = %default]")
p.add_option("--max-fails", dest="max_fails", type="int", default=-1, \
	help="exit when the number of failed configuration attempts exceeds N [default = no limit]")
p.add_option("--dot-file", dest="dot_file", type="string", default="", \
	help="write the dot-graph to the file specified (dot, gif, jpg, png, pdf supported). " + \
		"Note that if resolution fails, the last failed attempt will still produce an image. " + \
		"You can use --dot-file in combination with --max-fails to debug resolution failures.")
p.add_option("--print-env", dest="print_env", action="store_true", default=False, \
	help="print commands which, if run, would produce the configured environment [default = %default]")
p.add_option("--print-packages", dest="print_pkgs", action="store_true", default=False, \
	help="print resolved packages for this configuration [default = %default]")
p.add_option("--print-dot", dest="print_dot", action="store_true", default=False, \
	help="output a dot-graph representation of the configuration resolution [default = %default]")
p.add_option("--ignore-archiving", dest="ignore_archiving", action="store_true", default=False, \
	help="silently ignore packages that have been archived [default = %default]")
p.add_option("--ignore-blacklist", dest="ignore_blacklist", action="store_true", default=False, \
	help="include packages that are blacklisted [default = %default]")
p.add_option("--no-assume-dt", dest="no_assume_dt", action="store_true", default=False, \
	help="do not assume dependency transitivity [default = %default]")
p.add_option("--no-catch", dest="no_catch", action="store_true", default=False, \
	help="debugging option, turn on to see python exception on error [default = %default]")
p.add_option("-t", "--time", dest="time", default="0", \
	help="ignore packages newer than the given epoch time [default = current time]")
p.add_option("--no-path-append", dest="no_path_append", action="store_true", default=False, \
	help="don't append system-specific paths to PATH [default = %default]")
p.add_option("--wrapper", dest="wrapper", action="store_true", default=False, \
	help="set to true if creating a wrapper environment [default = %default]")
p.add_option("--print-launcher", dest="print_launcher", action="store_true", default=False, \
	help="print environment in launcher-like xml [default = %default]")

if (len(sys.argv) == 1):
	(opts, extraArgs) = p.parse_args(["-h"])
	sys.exit(0)

(opts, pkgstrs) = p.parse_args()

if opts.version:
	print os.getenv("REZ_VERSION")
	sys.exit(0)

if (opts.verbosity < 0) or (opts.verbosity > 2):
	sys.stderr.write("rez-config: error: option -v: invalid integer value: " + str(opts.verbosity) + '\n')
	sys.exit(1)

mode = None
if (opts.mode == "none"):
	mode = dc.RESOLVE_MODE_NONE
elif (opts.mode == "latest"):
	mode = dc.RESOLVE_MODE_LATEST
elif (opts.mode == "earliest"):
	mode = dc.RESOLVE_MODE_EARLIEST
else:
	sys.stderr.write("rez-config: error: option -m: illegal resolution mode '" + opts.mode + "'\n")
	sys.exit(1)

# force quiet with some options
do_quiet = opts.quiet or opts.print_env or opts.print_launcher or opts.print_pkgs or opts.print_dot


# validate time
time_epoch = int(opts.time)


#################################################################################
# MISC STUFF
#################################################################################

def pkg_not_found(pkg_req):
	syspaths = dc.get_system_package_paths()

	# check to see if it exists but it's archived
	if filesys.g_use_blacklist:
		filesys.enable_blacklist(False)
		found_path, found_ver = filesys.find_package2(syspaths, pkg_req.name, \
			dc.VersionRange(pkg_req.version), mode, time_epoch)
		if found_path != None:
			sys.stderr.write(pkg_req.short_name() + " exists but is blacklisted.\n")
			return

	if filesys.g_use_archiving:
		filesys.enable_archiving(False)
		found_path, found_ver = filesys.find_package2(syspaths, pkg_req.name, \
			dc.VersionRange(pkg_req.version), mode, time_epoch)
		if found_path != None:
			sys.stderr.write(pkg_req.short_name() + " exists but is archived.\n")
			return

	sys.stderr.write("Could not find the package '" + pkg_req.short_name() + "'\n")


##########################################################################################
# global initialisation
##########################################################################################

filesys.enable_blacklist(not opts.ignore_blacklist)
filesys.enable_archiving(not opts.ignore_archiving)


##########################################################################################
# construct package request
##########################################################################################

pkg_reqs = []

if not opts.no_os:
	import platform
	osname = platform.system()
	ospkg = ""

	if osname == "Linux":
		ospkg = "Linux"
	elif osname == "Darwin":
		ospkg = "Darwin"

	if ospkg == "":
		sys.stderr.write("Warning: Unknown operating system '" + ospkg + "'\n")
	elif ospkg not in pkgstrs:
		pkg_reqs.append(dc.str_to_pkg_req(ospkg))

for pkgstr in pkgstrs:
	pkg_reqs.append(dc.str_to_pkg_req(pkgstr))


##########################################################################################
# do the resolve
##########################################################################################

if opts.no_catch:
	pkg_ress, env_cmds, dot_graph, num_fails = \
		dc.resolve_packages(pkg_reqs, mode, do_quiet, opts.verbosity, opts.max_fails, \
		time_epoch, opts.no_path_append, opts.buildreqs, not opts.no_assume_dt, opts.wrapper)
else:
	try:
		pkg_ress, env_cmds, dot_graph, num_fails = \
			dc.resolve_packages(pkg_reqs, mode, do_quiet, opts.verbosity, opts.max_fails, \
			time_epoch, opts.no_path_append, opts.buildreqs, not opts.no_assume_dt, opts.wrapper)

	except dc.PkgSystemError, e:
		sys.stderr.write(str(e)+'\n')
		sys.exit(1)
	except dc.VersionError, e:
		sys.stderr.write(str(e)+'\n')
		sys.exit(1)
	except dc.PkgFamilyNotFoundError, e:
		sys.stderr.write("Could not find the package family '" + e.family_name + "'\n")
		sys.exit(1)
	except dc.PkgNotFoundError, e:
		pkg_not_found(e.pkg_req)
		sys.exit(1)
	except dc.PkgConflictError, e:
		sys.stderr.write("The following conflicts occurred:\n")
		for c in e.pkg_conflicts:
			sys.stderr.write(str(c)+'\n')

		# we still produce a dot-graph on failure
		if (e.last_dot_graph != ""):
			if (opts.dot_file != ""):
				gen_dotgraph_image(e.last_dot_graph, opts.dot_file)
			if opts.print_dot:
				print(e.last_dot_graph)

		sys.exit(1)
	except dc.PkgsUnresolvedError, e:
		sys.stderr.write("The following packages could not be resolved:\n")
		for p in e.pkg_reqs:
			sys.stderr.write(str(p)+'\n')
		sys.exit(1)
	except dc.PkgCommandError, e:
		sys.stderr.write("There was a problem with the resolved command list:\n")
		sys.stderr.write(str(e)+'\n')
		sys.exit(1)
	except dc.PkgCyclicDependency, e:
		sys.stderr.write("\nCyclic dependency(s) were detected:\n")
		sys.stderr.write(str(e) + "\n")

		# write graphs to file
		tmpf = tempfile.mkstemp(suffix='.dot')
		os.write(tmpf[0], str(e))
		os.close(tmpf[0])
		sys.stderr.write("\nThis graph has been written to:\n")
		sys.stderr.write(tmpf[1] + "\n")

		tmpf = tempfile.mkstemp(suffix='.dot')
		os.write(tmpf[0], e.dot_graph)
		os.close(tmpf[0])
		sys.stderr.write("\nThe whole graph (with cycles highlighted) has been written to:\n")
		sys.stderr.write(tmpf[1] + "\n")

		# we still produce a dot-graph on failure
		if (opts.dot_file != ""):
			gen_dotgraph_image(e.dot_graph, opts.dot_file)
		if opts.print_dot:
			print(e.dot_graph)

		sys.exit(1)

	except dc.PkgConfigNotResolvedError, e:
		sys.stderr.write("The configuration could not be resolved:\n")
		for p in e.pkg_reqs:
			sys.stderr.write(str(p)+'\n')
		sys.stderr.write("The failed configuration attempts were:\n")
		for s in e.fail_config_list:
			sys.stderr.write(s+'\n')

		# we still produce a dot-graph on failure
		if (opts.dot_file != ""):
			gen_dotgraph_image(e.last_dot_graph, opts.dot_file)
		if opts.print_dot:
			print(e.last_dot_graph)

		sys.exit(1)


##########################################################################################
# print result
##########################################################################################

if not do_quiet:
	print "\nsuccessful configuration found after " + str(num_fails) + " failed attempts."

if opts.print_env:
	for env_cmd in env_cmds:
		print env_cmd

if opts.print_pkgs:
	for pkg_res in pkg_ress:
		print pkg_res.short_name()

if opts.print_dot:
	print(dot_graph)

if (opts.dot_file != ""):
	gen_dotgraph_image(dot_graph, opts.dot_file)


#################################################################################
# LAUNCHER MIGRATION STUFF, DELETE WHEN LAUNCHER IS RETIRED
#################################################################################

if opts.print_launcher:

	print "<!-- THIS XML CONTENT WAS AUTO-GENERATED BY REZ -->"

	for cmd in env_cmds:
		if (cmd.find("CMAKE_MODULE_PATH") != -1):
			continue

		xml = cmd.replace("export ", "")
		toks = xml.split('=')
		if (len(toks) != 2):
			print "FIXME: " + cmd
			continue

		varname = toks[0]
		val = toks[1]
		action = "set"

		valtoks = val.split(':')
		if (len(valtoks) == 2):
			if (valtoks[0] == '$'+varname):
				action = "add"
				val = valtoks[1]

		xml = '<' + action + ' key="' + varname + '">' + val + '</' + action + '>'

		print xml











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
