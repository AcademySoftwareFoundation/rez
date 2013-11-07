'''
List information about a package.

Can operate on a particular package, or the latest version of every package
found in the given directory, or the default central packages directory if none is
specified.
'''

import os
import os.path
import sys
from rez.cli import error, output

def setup_parser(parser):
    parser.add_argument("package", metavar="PACKAGE", default=None, nargs='?',
                        help="specific package to list info on")
    parser.add_argument("-p", "--path", dest="path", default=os.environ["REZ_RELEASE_PACKAGES_PATH"],
                        help="path where packages are located")
    parser.add_argument("-n", "--no-missing", dest="nomissing", action="store_true", default=False,
                        help="don't list packages that are missing any of the requested fields")
    parser.add_argument("--auth", dest="auth", action="store_true", default=False,
                        help="list package authors")
    parser.add_argument("--desc", dest="desc", action="store_true", default=False,
                        help="list package description")
    parser.add_argument("--dep", dest="dep", action="store_true", default=False,
                        help="list package dependencies")

def command(opts):
    import rez.sigint as sigint
    from rez.packages import pkg_name, iter_version_packages

    #(opts, args) = p.parse_args()
    if not os.path.isdir(opts.path):
        sys.stderr.write("'" + opts.path + "' is not a directory.\n")
        sys.exit(1)

    for pkg in iter_version_packages(opts.package, opts.path):
        ln = pkg.base
        if opts.auth:
            ln = ln + " | "
            if "authors" in pkg.metadata:
                ln += " ".join(pkg.metadata["authors"])

        if opts.desc:
            ln = ln + " | "
            if "description" in pkg.metadata:
                descr = str(pkg.metadata["description"]).strip()
                descr = descr.replace('\n', "\\n")
                ln += descr

        if opts.dep:
            ln = ln + " | "
            reqs = pkg.metadata.get("requires", [])
            variants = pkg.metadata.get("variants", [])
            if len(reqs) + len(vars) > 0:
                deps = set([pkg_name(pkg) for pkg in reqs])
                for pkg_list in variants:
                    deps = deps | set([pkg_name(pkg) for pkg in pkg_list])

                if len(deps) > 0:
                    ln += "*" + " *".join(deps)

        output(ln)








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
