#!!REZ_PYTHON_BINARY!

#
# List information about a particular package, or the latest version of every package
# found in the given directory, or the default central packages directory if none is
# specified.
#

import os
import os.path
import sys
import optparse
import yaml
import sigint

import rez_filesys as fs


p = optparse.OptionParser()
p.add_option("-p", "--path", dest="path", default=os.environ["REZ_RELEASE_PACKAGES_PATH"], \
	help="path where packages are located [default = %default]")
p.add_option("--package", dest="package", default=None, \
	help="specific package to list info on [default = %default]")
p.add_option("-n", "--no-missing", dest="nomissing", action="store_true", default=False, \
	help="don't list packages that are missing any of the requested fields [default = %default]")
p.add_option("--auth", dest="auth", action="store_true", default=False, \
	help="list package authors [default = %default]")
p.add_option("--desc", dest="desc", action="store_true", default=False, \
	help="list package description [default = %default]")
p.add_option("--dep", dest="dep", action="store_true", default=False, \
	help="list package dependencies [default = %default]")
p.add_option("--vers", dest="vers", action="store_true", default=False, \
	help="list package versions [default = %default]")

(opts, args) = p.parse_args()


if not os.path.isdir(opts.path):
	sys.stderr.write("'" + opts.path + "' is not a directory.\n")
	sys.exit(1)

pkg_paths = []

if opts.package:
	fullpath = os.path.join(opts.path, opts.package)
	if not os.path.isdir(fullpath):
		sys.stderr.write("'" + fullpath + "' is not a directory.\n")
		sys.exit(1)
	pkg_paths = [fullpath]
else:
	for f in os.listdir(opts.path):
		if (f == "rez"):
			continue

		fullpath = os.path.join(opts.path, f)
		if os.path.isdir(fullpath):
			pkg_paths.append(fullpath)


for fullpath in pkg_paths:

	vers = [x for x in fs.get_versions_in_directory(fullpath, False)]
	if vers:
		filename = fullpath + '/' + str(vers[-1][0]) + "/package.yaml"
		metadict = yaml.load(open(filename).read())

		ln = fullpath.split('/')[-1]

		if opts.auth:
			ln = ln + " | "
			if "authors" in metadict:
				ln = ln + str(" ").join(metadict["authors"])
			else:
				continue

		if opts.desc:
			ln = ln + " | "
			if "description" in metadict:
				descr = str(metadict["description"]).strip()
				descr = descr.replace('\n', "\\n")
				ln = ln + descr
			else:
				continue

		if opts.dep:
			ln = ln + " | "
			reqs = metadict["requires"] if ("requires" in metadict) else []
			vars = metadict["variants"] if ("variants" in metadict) else []
			if len(reqs) + len(vars) > 0:

				fn_unver = lambda pkg: pkg.split('-')[0]
				deps = set(map(fn_unver, reqs))
				for var in vars:
					deps = deps | set(map(fn_unver, var))

				if len(deps) > 0:
					ln = ln + "*" + str(" *").join(deps)
					
		if opts.vers:
			ln = ln + " | "
			versions = [str(x[0]) for x in vers]
			if len(versions) > 0:
				ln = ln + "*" + str(" *").join(versions)
					
		print ln








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
