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
p.add_option("--no-cache", dest="no_cache", action="store_true", default=False, \
	help="disable caching [default = %default]")
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
p.add_option("--meta-info", dest="meta_info", type="string", \
    help="Bake metadata into env-vars. Eg: --meta-info=tools,priority")
p.add_option("--meta-info-shallow", dest="meta_info_shallow", type="string", \
    help="Same as --meta-info, but only bakes data for directly requested packages.")
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
do_quiet = opts.quiet or opts.print_env or opts.print_pkgs or opts.print_dot

# validate time
time_epoch = int(opts.time)

# parse out meta bake
meta_vars = (opts.meta_info or '').replace(',',' ').strip().split()
shallow_meta_vars = (opts.meta_info_shallow or '').replace(',',' ').strip().split()



##########################################################################################
# construct package request
##########################################################################################
resolver = dc.Resolver(mode, do_quiet, opts.verbosity, opts.max_fails, time_epoch, \
	opts.buildreqs, not opts.no_assume_dt, not opts.no_cache)

if opts.no_catch:
	pkg_reqs = [dc.str_to_pkg_req(x) for x in pkgstrs]
	pkg_ress, env_cmds, dot_graph, num_fails = resolver.resolve(pkg_reqs, opts.no_os, \
		opts.no_path_append, opts.wrapper, meta_vars, shallow_meta_vars)
else:
	result = resolver.guarded_resolve(pkgstrs, opts.no_os, opts.no_path_append, opts.wrapper, \
		meta_vars, shallow_meta_vars, opts.dot_file, opts.print_dot)

	if not result:
		sys.exit(1)
	pkg_ress, env_cmds, dot_graph, num_fails = result



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
