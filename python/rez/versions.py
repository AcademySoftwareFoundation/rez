"""
This module contains classes which operate on version strings. Example version strings include:
'', '1', '1.2.3', '3.5+', '3.5+<4', '10.5|11.2', '10.5|11+', '1.2.a'.
Character components are allowed, and are ordered alphabetically, ie '1.b' > '1.a', however if
a component is a valid number then it is treated numerically, not alphabetically. Only single
characters 'a'-'z' are allowed.

Operations such as unions and intersections are possible. For example, the version '10.5' is
considered the superset of any version of the form '10.5.x', so union(10.5, 10.5.4) would be
'10.5'.

A single version string can describe sets of disparate version ranges - for example, '10.5|5.4|7'.
A version is said to be 'inexact' if it definitely describes a range of versions, for example
'4.5+', '1.0|2.0', '', '4.5+<5.0'. A version string is never said to be 'exact', because whether
this is true depends on context - for example the version '10.5' may represent an exact version
in one case, but may represent the superset of all versions '10.5.x' in another.
"""

import re


class VersionError(Exception):
	"""
	Exception
	"""
	def __init__(self, value=None):
		self.value = value
	def __str__(self):
		return "Invalid version: %s" % self.value

class Version(object):
	"""
	A version string. Note that disparate version ranges (separated with '|'s) are not supported -
	use a VersionRange for this.
	"""

	INF 	= [  999999 ]
	NEG_INF = [ -999999 ]
	valid_char = re.compile("^[a-z]$")

	def __init__(self, version_str=None, ge_lt=None):
		if version_str:
			try:
				version_str = str(version_str)
			except UnicodeEncodeError:
				raise VersionError("Non-ASCII characters in version string")

			rangepos = version_str.find("+<")
			if (rangepos == -1):
				plus = version_str.endswith('+')
				tokens = version_str.rstrip('+').replace('-', '.').split('.')
				self.ge = []
				for tok in tokens:
					self.to_comp(tok, version_str)

				if plus:
					self.lt = Version.INF
				else:
					self.lt = self.get_ge_plus_one()

				if len(self.ge) == 0:
					self.ge = Version.NEG_INF

			else:
				v1 = Version(version_str[:rangepos])
				v2 = Version(version_str[rangepos+2:])
				self.ge = v1.ge
				self.lt = v2.ge

				# remove trailing zeros on lt bound (think: 'A < 1.0.0' == 'A < 1')
				# this also makes this version invalid: '1+<1.0.0'
				while (len(self.lt) > 1) and (self.lt[-1] == 0):
					self.lt.pop()

				if self.lt <= self.ge:
					raise VersionError("lt<=ge: "+version_str)
		elif ge_lt:
			self.ge = ge_lt[0][:]
			self.lt = ge_lt[1][:]
		else:
			self.ge = Version.NEG_INF
			self.lt = Version.INF

	def copy(self):
		return Version(ge_lt=(self.ge, self.lt))

	def to_comp(self, tok, version_str):
		if len(tok) == 0:
			raise VersionError(version_str)

		if (tok[0] == '0') and (tok != '0'):  # zero-padding is not allowed, eg '03'
			raise VersionError(version_str)

		try:
			i = int(tok)
			if i < 0:
				raise VersionError("Can't have negative components: "+version_str)
			self.ge.append(i)
		except ValueError:
			if self.is_tok_single_letter(tok):
				self.ge.append(tok)
			else:
				raise VersionError("Invalid version '%s'" % version_str)

	def is_tok_single_letter(self, tok):
		return Version.valid_char.match(tok) is not None

	def get_ge_plus_one(self):
		if len(self.ge) == 0:
			return Version.INF
		if self.ge == Version.NEG_INF:
			return Version.INF
		v = self.ge[:]
		v.append(self.inc_comp(v.pop()))
		return v

	def is_inexact(self):
		"""
		Return true if version is inexact. e.g. '10.5+' or '10.5+<10.7'
		
		.. note:: not is_inexact() does not imply exact - for
		eg, the version '10.5' *may* refer to any version of '10.5.x', but we
		cannot know this without inspecting the package. Thus, the Version class
		on its own can only know when it is inexact, and never when it is exact.
		"""
		if len(self.lt)==0 and len(self.ge)==0:
			return True
		return self.lt != self.get_ge_plus_one()

	def is_any(self):
		"""
		Return true if version is 'any', ie was created from an empty string
		"""
		return self.ge == Version.NEG_INF and self.lt == Version.INF

	def inc_comp(self,comp):
		"""
		increment a number or single character by 1
		"""
		if type(comp) == type(1):
			return comp + 1
		else:
			return chr(ord(comp) + 1)

	def contains_version(self, version):
		"""
		Returns True if the exact version (eg 1.0.0) is contained within this range.
		
		accepts a Version instance or a version ge.
		"""
		# allow a ge to be passed directly
		if isinstance(version, Version):
			ge = version.ge
		return (ge >= self.ge) and (ge < self.lt)

	def get_union(self, ver):
		"""
		Return new version(s) representing the union of this and another version.
		The result may be more than one version, so a version list is returned.
		"""
		if self.ge >= ver.lt or self.lt <= ver.ge:
			return [ self.copy(), ver.copy() ]
		v = Version('')
		v.ge = min( [self.ge, ver.ge] )[:]
		v.lt = max( [self.lt, ver.lt] )[:]
		return [v]

	def get_intersection(self, ver):
		"""
		Return a new version representing the intersection between this and
		another version, or None if the versions do not overlap
		"""
		if ver.ge >= self.lt or ver.lt <= self.ge:
			return None

		ver_int = Version('')
		if ver.ge > self.ge:
			ver_int.ge = ver.ge[:]
		else:
			ver_int.ge = self.ge[:]
		if ver.lt < self.lt:
			ver_int.lt = ver.lt[:]
		else:
			ver_int.lt = self.lt[:]
		return ver_int

	def __str__(self):
		def get_str(parts):
			return ".".join([str(part) for part in parts])

		if self.lt == Version.INF:
			if self.ge == Version.NEG_INF:
				return ""
			else:
				return get_str(self.ge) + "+"
		elif self.is_inexact():
			return get_str(self.ge) + "+<" + get_str(self.lt)
		else:
			return get_str(self.ge)

	def __repr__(self):
		return "%s('%s')" % (self.__class__.__name__, self)

	def __lt__(self, ver):
		"""
		less-than test. Version A is < B if A's ge bound is < B's. If the ge
		bounds are the same, the lt bounds are then tested, and A is < B if its
		lt bound is < B's.
		"""
		return self.lt < ver.lt if self.ge == ver.ge else self.ge < ver.ge

	def __eq__(self, ver):
		return self.ge == ver.ge and self.lt == ver.lt

	def __le__(self, ver):
		return self.__lt__(ver) or self.__eq__(ver)


class VersionRange(object):
	"""
	A collection of zero or more inexact versions, which do not overlap. If a
	VersionRange is initialised with disparate version ranges which do overlap
	(eg '10.5+|10.5.2'), these will be resolved at initialization.
	"""

	def __init__(self, v="", _versions=None):
		if _versions:
			self.versions = [x.copy() for x in _versions]
		else:
			# just make sure it's a string, because sometimes we pass in a Version instance
			version_str = str(v)
			version_strs = version_str.split("|")
			versions = []
			for vstr in version_strs:
				versions.append(Version(vstr))

			self.versions = get_versions_union(versions)

	def copy(self):
		return VersionRange(_versions=self.versions)

	def contains_version(self, version):
		"""
		Returns True if the exact version (eg 1.0.0) is contained within this range.
		"""
		for ver in self.versions:
			if ver.contains_version(version):
				return True
		return False

	def matches_version(self, ver, allow_inexact=False):
		"""
		Returns True if the range matches the Version.
		
		If `allow_inexact` is True, considers inexact matches as well. 
		"""
		# if the range is not inexact, then there is only one version
		if not self.is_inexact() and ver == self.versions[0]:
			return True
		# Note that VersionRange('').contains_version('10') == True
		if allow_inexact and self.contains_version(ver):
			return True
		return False

	def get_union(self, vers):
		"""
		get union
		"""
		vers_union = VersionRange('')
		vers_union.versions = get_versions_union(self.versions + vers.versions)
		vers_union.versions.sort()
		return vers_union

	def get_intersection(self, vers):
		"""
		get intersection, return None if there are no intersections
		"""
		vers_int = VersionRange('')
		vers_int.versions = []
		for ver in self.versions:
			for ver2 in vers.versions:
				vint = ver.get_intersection(ver2)
				if vint:
					vers_int.versions.append(vint)

		if (len(vers_int.versions) == 0):
			return None
		else:
			vers_int.versions.sort()
			return vers_int


	def get_inverse(self):
		"""
		get the inverse of this version range
		"""
		if self.is_any():
			vers_none = VersionRange('')
			vers_none.versions = []
			return vers_none

		# the inverse of none is any
		if self.is_none():
			return VersionRange('')

		# inverse is the ranges between existing ranges
		vers_inv = VersionRange('')
		vers_inv.versions = []

		ver_front = Version("")
		ver_front.ge = Version.NEG_INF
		ver_front.lt = [Version.NEG_INF[0] + 1]
		ver_back = Version("")
		ver_back.ge = Version.INF
		ver_back.lt = [Version.INF[0] + 1]

		vers = [ver_front] + self.versions + [ver_back]
		for i in range(0, len(vers)-1):
			v0 = vers[i]
			v1 = vers[i+1]
			if v0.lt < v1.ge:
				v = Version("")
				v.ge, v.lt = v0.lt, v1.ge
				vers_inv.versions.append(v)

		if len(vers_inv.versions) > 0:
			# clamp ge limits back to zero
			if vers_inv.versions[0].lt <= [0]:
				vers_inv.versions = vers_inv.versions[1:]

			if len(vers_inv.versions) > 0 and vers_inv.versions[0].ge < [0]:
				vers_inv.versions[0].ge = [0]
				# we may get something like this when clamping: 0+<0.0, which
				# is not valid, so detect it and remove it
				while (len(vers_inv.versions[0].lt) > 1) and (vers_inv.versions[0].lt[-1] == 0):
					vers_inv.versions[0].lt.pop()
				if vers_inv.versions[0].lt == vers_inv.versions[0].ge:
					vers_inv.versions.pop(0)

		return vers_inv

	def is_greater_no_overlap(self, ver):
		"""
		return True if the given version range is greater than this one,
		and there is no overlap
		"""
		if len(self.versions) == 0 and len(ver.versions) == 0:
			return False
		elif len(self.versions) == 0 or len(ver.versions) == 0:
			return True
		return ver.versions[0].ge >= self.versions[-1].lt

	def is_inexact(self):
		"""
		return True if the version range is inexact
		"""
		if len(self.versions) == 0:
			return False
		return (len(self.versions) > 1) or self.versions[0].is_inexact()

	def is_any(self):
		"""
		Return true if version is 'any', ie was created from an empty string
		"""
		return (len(self.versions) == 1) and self.versions[0].is_any()

	def is_none(self):
		"""
		Return true if this range describes no versions
		"""
		return len(self.versions) == 0

	def get_dim(self):
		"""
		Returns the number of distinct versions in the range
		"""
		return len(self.versions)

	def __str__(self):
		return "|".join(str(v) for v in self.versions)

	def __repr__(self):
		return "%s('%s')" % (self.__class__.__name__, self)

	def __eq__(self, ver):
		"""
		equality test
		"""
		if ver is None:
			return False
		return self.versions == ver.versions

	def __ne__(self, ver):
		"""
		inequality test
		"""
		return not self == ver

def get_versions_union(versions):
	nvers = len(versions)
	if nvers == 0:
		return []
	elif nvers == 1:
		return [x.copy() for x in versions]
	elif nvers == 2:
		return versions[0].get_union(versions[1])
	else:
		new_versions = []
		idx = 1
		versions_tmp = sorted([x.copy() for x in versions])
		for ver1 in versions_tmp:
			overlap = False
			for ver2 in versions_tmp[idx:]:
				ver_union = ver1.get_union(ver2)
				if len(ver_union) == 1:
					ver2.ge, ver2.lt = ver_union[0].ge, ver_union[0].lt
					overlap = True
					break
			if not overlap:
				new_versions.append(ver1)
			idx += 1
		return new_versions



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
