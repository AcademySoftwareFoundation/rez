"""
Public enums
"""

REZ_PACKAGES_PATH_ENVVAR = "REZ_PACKAGES_PATH"

PKG_METADATA_FILENAME = "package.yaml"

PRIMARY_SEPARATOR = '@' # defines the boundary between a package name string and the version string

# Resolve modes, used in resolve_packages()
# If resolution of a package list results in packages with inexact versions, then:
#
# Check the file system - if packages exist within the inexact version range,
# then use the latest to disambiguate
RESOLVE_MODE_LATEST = 	0
# Check the file system - if packages exist within the inexact version range,
# then use the earliest to disambiguate
RESOLVE_MODE_EARLIEST =	1
# don't try and resolve further, and raise an exception
RESOLVE_MODE_NONE = 	2

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
