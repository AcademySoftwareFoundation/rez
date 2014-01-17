'''
Print the path to a package.
'''
import sys
from rez.cli import error, output

def setup_parser(parser):
    parser.add_argument("pkg", metavar='PACKAGE',
                        help="package name")
# pkg = sys.argv[1]

def command(opts, parser=None):
    from rez.packages import split_name, package_in_range
    try:
        pkg = package_in_range(*split_name(opts.pkg))
    except Exception:
        output("package not found: '" + opts.pkg + "'")
        sys.exit(1)
    else:
        output(pkg.base)

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
