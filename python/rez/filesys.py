"""
filesystem-related functions
"""

from versions import *
from public_enums import *
from rez_exceptions import *
import string
import os
import sys
import yaml

dir_exist_entries = {}
file_exist_entries = {}
versions_entries = [ {}, {} ]
g_use_blacklist = False
g_use_archiving = False

# TODO branches are deprecated
ignore_branches = True

_g_local_pkgs_path 				= os.getenv("REZ_LOCAL_PACKAGES_PATH")
_g_old_timestamp_behaviour 		= os.getenv("REZ_OLD_TIMESTAMP_BEHAVIOUR")


def enable_blacklist(enable):
	global versions_entries
	global g_use_blacklist
	g_use_blacklist = enable
	versions_entries = [ {}, {} ]


def enable_archiving(enable):
	global versions_entries
	global g_use_archiving
	g_use_archiving = enable
	versions_entries = [ {}, {} ]


def dir_exists(path):
	"""
	Return True if the directory exists, False if not, and cache the result
	"""
	global dir_exist_entries
	exists = dir_exist_entries.get(path)
	if (exists == None):
		exists = os.path.isdir(path)
		dir_exist_entries[path] = exists
	return exists


def file_exists(filepath):
	"""
	Return True if the file exists, False if not, and cache the result
	"""
	global file_exist_entries
	exists = file_exist_entries.get(filepath)
	if (exists == None):
		exists = os.path.isfile(filepath)
		file_exist_entries[filepath] = exists
	return exists


def get_versions_in_directory(path, ascending, time_epoch=0, warnings=True):
	"""
	For a given directory, return a list of VersionRanges, in specified order,
	which match version directories found in the given directory (caches the result)
	"""
	global versions_entries
	global g_use_blacklist

	if ascending:
		versdict = versions_entries[0]
	else:
		versdict = versions_entries[1]

	versions = versdict.get(path)
	if versions is None:
		# load archive/blacklist info
		pkg_ignore_ver_range = None
		if g_use_blacklist or g_use_archiving:
			packages_file = path + "/packages.yaml"
			if file_exists(packages_file):
				metadict = yaml.load(open(packages_file).read())
				if metadict != None:
					if g_use_blacklist and "blacklist" in metadict:
						pkg_ignore_ver_range = VersionRange(str("|").join(metadict["blacklist"]))
					if g_use_archiving and "archive" in metadict:
						ver_range = VersionRange(str("|").join(metadict["archive"]))
						if pkg_ignore_ver_range:
							pkg_ignore_ver_range = pkg_ignore_ver_range.get_union(ver_range)
						else:
							pkg_ignore_ver_range = ver_range

		versions = []
		for f in os.listdir(path):
			fullpath = os.path.join(path, f)
			if os.path.isdir(fullpath):
				try:
					ver = Version(f)
				except Exception:
					# dir that isn't correct version format, assume it's something else
					continue

				# braches - deprecated
				if ver.is_branch() and ignore_branches:
					continue

				# skip based on archiving/blacklist
				if pkg_ignore_ver_range:
					ver_union = pkg_ignore_ver_range.get_union(VersionRange(f))
					if(ver_union == pkg_ignore_ver_range):
						continue

				if not os.access(fullpath + '/' + PKG_METADATA_FILENAME, os.F_OK):
					# dir missing a package.yaml
					if warnings:
						sys.stderr.write("Warning: ignoring package with missing " + \
							PKG_METADATA_FILENAME + ": " + fullpath + '\n')
					continue

				is_local_pkg = fullpath.startswith(_g_local_pkgs_path)
				if not is_local_pkg:
					# check that the package is timestamped
					release_time_f = fullpath + '/.metadata/release_time.txt'
					is_timestamped = os.access(release_time_f, os.F_OK)

					if not is_timestamped and not _g_old_timestamp_behaviour:
						s = "Warning: The package at %s is not timestamped and will be ignored. " + \
							"To timestamp it manually, use the rez-timestamp utility."
						print >> sys.stderr, s % fullpath
						continue

					if (time_epoch > 0):
						# skip package if it is newer than the specified time-date
						if is_timestamped:
							f = open(release_time_f, 'r')
							pkg_time_epoch_str = f.read().strip()
							f.close()
							pkg_time_epoch = int(pkg_time_epoch_str)
						else:
							# old behaviour - non-timestamped package is always visible
							pkg_time_epoch = 0

						if pkg_time_epoch > time_epoch:
							continue

				versions.append(ver)

		versions.sort()
		if not ascending:
			versions.reverse()

		versdict[path] = versions

	return versions


def find_package(family_path, ver_range, mode, time_epoch=0):
	"""
	Given a path to a package family, a (possibly inexact) version range, and a resolution mode,
	return the resolved version, or None if not found. An exception will be raised if RESOLVE_MODE_NONE
	is used.

	Eg assuming:
	.../foo/1.3.2/package.yaml
	.../foo/1.3.1/package.yaml
	.../foo/1.3.0/package.yaml

	find_package('.../foo', 1.3, RESOLVE_MODE_LATEST) == 1.3.2
	find_package('.../foo', 1.3, RESOLVE_MODE_EARLIEST) == 1.3.0
	find_package('.../foo', 2, RESOLVE_MODE_EARLIEST) == None
	find_package('.../foo', '', RESOLVE_MODE_LATEST) == 1.3.2
	find_package('.../foo', '1.3.2.2', RESOLVE_MODE_LATEST) == None
	"""

	# check base path exists
	if not dir_exists(family_path):
		return None

	if ver_range.is_any():
		# check for special case - unversioned package
		if file_exists(family_path + '/' + PKG_METADATA_FILENAME):
			return Version("")

	do_ascending = (mode == RESOLVE_MODE_EARLIEST)
	dir_vers = get_versions_in_directory(family_path, do_ascending, time_epoch)

	if not ver_range.is_inexact():
		# check in case ver is already exact
		if ver_range.versions[0] in dir_vers:
			return ver_range.versions[0]

	if (mode == RESOLVE_MODE_NONE):
		return None

	# find the earliest/latest version on disk that falls within ver
	# todo binary search?
	for ver in dir_vers:
		ver_r = VersionRange(str(ver))
		pruned_range = ver_range.get_pruned_versions(ver)
		inters = pruned_range.get_intersection(ver_r)

		if inters:
			# catch case where we're searching for 'foo-1.2.3', but only 'foo-1.2' exists
			# (ie, a subset of an exact version)
			if inters == ver_r:
				return ver

	return None


def find_package2(package_paths, family_name, ver_range, mode, time_epoch=0):
	"""
	Given a list of package paths, a family name, a (possibly inexact) version range, and a resolution
	mode, return the family path and resolved version, or None,None if not found. An exception will be
	raised if RESOLVE_MODE_NONE is used. If two versions in two different paths are the same, then the
	package in the first path is returned in preference.
	"""
	maxminver = None
	fpath = None

	for pkg_path in package_paths:
		family_path = pkg_path + '/' + family_name
		ver2 = find_package(family_path, ver_range, mode, time_epoch)
		if ver2:
			if (mode == RESOLVE_MODE_LATEST):
				if maxminver:
					if (maxminver.ge < ver2.ge):
						maxminver = ver2
						fpath = family_path
				else:
					maxminver = ver2
					fpath = family_path
			else:	# earliest
				if maxminver:
					if (maxminver.ge > ver2.ge):
						maxminver = ver2
						fpath = family_path
				else:
					maxminver = ver2
					fpath = family_path

	return fpath, maxminver


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
