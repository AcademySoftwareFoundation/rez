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

import copy
import re

class VersionError(Exception):
	"""
	Exception
	"""
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return "Invalid version: %s" % self.value

class Version:
	"""
	A version string. Note that disparate version ranges (separated with '|'s) are not supported -
	use a VersionRange_Old for this.
	"""

	INF 	= [  999999 ]
	NEG_INF = [ -999999 ]
	valid_branch = re.compile("^[A-Za-z][A-Za-z0-9_]+$")
	valid_char = re.compile("^[a-z]$")

	def __init__(self, version_str = ""):
		try:
			version_str = str(version_str)
		except UnicodeEncodeError:
			raise VersionError("Non-ASCII characters in version string (and that means i can't print it!)")
		if len(version_str) > 0:
			rangepos = version_str.find("+<")
			if (rangepos == -1):
				self.root_version = None
				self.branch_string = None

				plus = version_str.endswith('+')
				tokens = version_str.rstrip('+').replace('-', '.').split('.')
				self.ge = []
				for tok in tokens:
					self.to_comp(tok, version_str)

				if plus:
					if len(self.ge) == 0 and self.is_branch():
						raise VersionError("Can't have '+' there: "+version_str)

					self.lt = Version.INF
				else:
					self.lt = self.get_ge_plus_one()

				if len(self.ge) == 0:
					self.ge = Version.NEG_INF

			else:
				v1 = Version(version_str[:rangepos])
				v2 = Version(version_str[rangepos+2:])
				if v1.branch_string is None and v2.branch_string is None:
					self.root_version = None
					self.branch_string = None
					self.ge = v1.ge
					self.lt = v2.ge
				elif v1.branch_string is not None and v2.branch_string is not None:
					if v1.branch_string == v2.branch_string and \
							v1.root_version == v2.root_version:
						self.root_version = v1.root_version
						self.branch_string = v1.branch_string
						self.ge = v1.ge
						self.lt = v2.ge
					else:
						raise VersionError("Must both be same branch: "+version_str)
				else:
					raise VersionError("Must both be in branch: "+version_str)

				# remove trailing zeros on lt bound (think: 'A < 1.0.0' == 'A < 1')
				# this also makes this version invalid: '1+<1.0.0'
				while (len(self.lt) > 1) and (self.lt[-1] == 0):
					self.lt.pop()

				if self.lt <= self.ge:
					raise VersionError("lt<=ge: "+version_str)

		else:
			self.ge = Version.NEG_INF
			self.lt = Version.INF
			self.root_version = None
			self.branch_string = None

		if self.root_version is not None and self.branch_string is not None:
			if len(self.root_version) == 0 and len(self.branch_string) > 0 and self.ge == Version.NEG_INF:
				raise VersionError("Branch must be associated with a concrete root version: "+version_str)

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
			elif type(tok) == type(str()):
				# here we branch
				if self.root_version:
					raise VersionError("Already have a branch part: "+version_str)
				if not self.is_valid_branch_string(tok):
					raise VersionError("Char not allowed in branch: "+version_str)
				self.branch_string = tok
				self.root_version = self.ge[:]
				self.ge = []

	def is_tok_single_letter(self, tok):
		return Version.valid_char.match(tok) is not None

	def is_valid_branch_string(self, tok):
		return Version.valid_branch.match(tok) is not None

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
		Return true if version is inexact. !is_inexact does not imply exact - for
		eg, the version '10.5' may refer to any version of '10.5.x'.
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

	def is_branch(self):
		"""
		Returns true if this Version is a branch. It *just* checks the branch_string.
		"""
		return self.branch_string is not None

	def same_branch(self, ver):
		"""
		Returns true if both versions are part of a branch and the it's the same one.
		"""
		return self.root_version == ver.root_version and \
				self.branch_string == ver.branch_string

	def get_union(self, ver):
		"""
		Return new version(s) representing the union of this and another version.
		The result may be more than one version, so a version list is returned.
		"""

		def get_union_impl(v1,v2):
			"""
			Assumes that v1 & v2 overlap, and returns that overlap by getting the
			lowest of both and highest of both. Copies the root_version & branch_string
			even if they are None
			"""
			if self.ge >= ver.lt or self.lt <= ver.ge:
				return [ copy.deepcopy(self), copy.deepcopy(ver) ]
			v = Version('')
			v.ge = min( [v1.ge, v2.ge] )[:]
			v.lt = max( [v1.lt, v2.lt] )[:]
			v.root_version = v1.root_version
			v.branch_string = v1.branch_string
			return [ v ]

		if self.is_branch() and ver.is_branch():
			# only if both in a branch (not trunk)
			if not self.same_branch(ver):
				return [ copy.deepcopy(self), copy.deepcopy(ver) ]

			if self.ge >= ver.lt or self.lt <= ver.ge:
				return [ copy.deepcopy(self), copy.deepcopy(ver) ]

			return get_union_impl(self,ver)

		if self.is_branch() or ver.is_branch():
			# The union of plain & branch is the whole plain plus
			# the part of the branch that does NOT intersect with the plain
			# so that would be:
			#  union = plain + ( branch - intersection ( branch, plain ) )
			# since we don't have the subtract operator, the operation becomes:
			#  union = plain + intersection( branch, inverse( intersection( branch, plain ) ) )

			plain = self if ver.is_branch() else ver
			branch = self if self.is_branch() else ver

			intersection = plain.get_intersection(branch)
			if intersection is None:
				return [ copy.deepcopy(self), copy.deepcopy(ver) ]
			inv = VersionRange(intersection).get_inverse()
			b = inv.get_intersection(VersionRange(branch))
			return [plain]+b.versions

		return get_union_impl(self,ver)

	def get_effective_version(self, which):
		"""
		The effective version of a branch is the root_version+branch_version. Eg:
		"1.4.br.0.2.5" -> 1.6.5 that is: 1+0=1,4+2=6,0+5=5
		If there is no branch, it will still calculate the same:
		"1.5.2" -> 1.5.2
		"""
		ver = []
		root_ver = self.root_version[:] if self.root_version is not None else []
		ge_ver = which[:]
		while (len(root_ver) + len(ge_ver)) > 0:
			n = 0
			if len(root_ver) > 0:
				n += root_ver[0]
				root_ver.pop(0)
			if len(ge_ver) > 0:
				n += ge_ver[0]
				ge_ver.pop(0)
			ver.append(n)
		return ver

	def is_concrete(self):
		"""
		A version is concrete if it can exist on disk - that can only happen for
		trunk or if the effective version is different from the root_version, eg:
		is_concrete(1.2.5.br.0.1.0) == True
		is_concrete(1.2.5.br.0.0.0) == False
		is_concrete(1.2.5.br.0.0.0.1) == True
		"""
		if not self.is_branch():
			return True
		return self.root_version != self.get_effective_version(self.ge)

	def get_first_diff(self):
		"""
		Get the position in the version part that has a change. A version is like this:
		1.4 -> 1.4+<1.5, so the position is 1
		1.4.5.4 -> 1.4.5.4+<1.4.5.5, position is 3
		1.3.5+<1.5, position is 1
		"""
		count = 0
		ge_ver = self.ge[:]
		lt_ver = self.lt[:]
		while len(ge_ver) > 0 and len(lt_ver) > 0:
			if len(ge_ver) > 0 and len(lt_ver) > 0:
				if ge_ver[0] != lt_ver[0]:
					return count
			ge_ver.pop(0)
			lt_ver.pop(0)
			count += 1
		return count

	def get_intersection(self, ver):
		"""
		Return a new version representing the intersection between this and
		another version, or None if the versions do not overlap
		"""
		def _get_intersection_impl(a,b):
			"""
			Internal implementation
			"""
			ver_int = Version('')
			ver_int.root_version = self.root_version
			ver_int.branch_string = self.branch_string
			if ver.ge > self.ge:
				ver_int.ge = ver.ge[:]
			else:
				ver_int.ge = self.ge[:]
			if ver.lt < self.lt:
				ver_int.lt = ver.lt[:]
			else:
				ver_int.lt = self.lt[:]
			return ver_int

		#######
		if self.is_branch() and ver.is_branch():

			if not self.same_branch(ver):
				return None
			else:
				if ver.ge >= self.lt or ver.lt <= self.ge:
					return None
				else:
					return _get_intersection_impl(self,ver)
		elif self.is_branch() or ver.is_branch():
			# the case where one is a branch and the other isn't

			plain = self if ver.is_branch() else ver # plain version
			branch = self if self.is_branch() else ver # branched version

			if branch.root_version < plain.ge or branch.root_version >= plain.lt:
				return None

			ver_int_fake = Version("")
			ver_int_fake.root_version = branch.root_version
			ver_int_fake.branch_string = branch.branch_string
			ver_int_fake.ge = [0 for i in range(plain.get_first_diff()+1)] if not plain.is_any() else []
			ver_int_fake.lt = ver_int_fake.get_ge_plus_one()

			ver_int = ver_int_fake.get_intersection(branch)

			return ver_int

		else:
			# no branch case
			if ver.ge >= self.lt or ver.lt <= self.ge:
				return None
			else:
				return _get_intersection_impl(self,ver)


	def __str__(self):
		def get_str(parts,prefix=None):
			if prefix:
				return ".".join([prefix]+[str(part) for part in parts])
			return ".".join([str(part) for part in parts])

		br_str = get_str(self.root_version+[self.branch_string]) if self.is_branch() else None
		if self.lt == Version.INF:
			if self.ge == Version.NEG_INF:
				return br_str if br_str else ""
			else:
				return get_str(self.ge,br_str) + "+"
		elif self.is_inexact():
			return get_str(self.ge,br_str) + "+<" + get_str(self.lt,br_str)
		else:
			return get_str(self.ge,br_str)

	def __lt__(self, ver):
		"""
		less-than test. Version A is < B if A's ge bound is < B's. If the ge
		bounds are the same, the lt bounds are then tested, and A is < B if its
		lt bound is < B's.
		"""
		def ge_lt(a,b):
			return a.lt < b.lt if a.ge == b.lt else a.ge < b.ge

		if self.root_version == ver.root_version:
			if self.branch_string == ver.branch_string:
				return ge_lt(self,ver)
			else:
				return self.branch_string < ver.branch_string
		else:
			return self.root_version < ver.root_version

	def __eq__(self, ver):
		"""
		equality test
		"""
		return self.ge == ver.ge and self.lt == ver.lt and \
			self.root_version == ver.root_version and \
			self.branch_string == ver.branch_string

	def __le__(self, ver):
		return self.__lt__(ver) or self.__eq__(ver)

class VersionRange:
	"""
	A collection of zero or more inexact versions, which do not overlap. If a
	VersionRange is initialised with disparate version ranges which do overlap
	(eg '10.5+|10.5.2'), these will be resolved at initialization.
	"""

	def __init__(self, v=""):
		# just make sure it's a string, because sometimes we pass in a Version instance
		version_str = str(v)
		version_strs = version_str.split("|")
		versions = []
		for vstr in version_strs:
			versions.append(Version(vstr))

		# sort first just to get them into branch-alike sorting
		versions.sort()
		self.versions = get_versions_union(versions)
		# and sort again to make sure we got things right after unioning
		self.versions.sort()

	def get_union(self, vers):
		"""
		get union
		"""
		vers_union = VersionRange('')
		vers_union.versions = get_versions_union(sorted(self.versions + vers.versions))
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

		def _get_root_branch(v):
			return '.'.join([str(s) for s in v.root_version+[v.branch_string]]) if v.is_branch() else ''

		if self.is_any():
			vers_none = VersionRange('')
			vers_none.versions = []
			return vers_none

		# the inverse of none is any
		if self.is_none():
			return VersionRange('')

		# inverse is the ranges between existing ranges

		# first, collect all versions into branches, so we can invert them
		branches = {}
		for v in self.versions:
			if v.is_any():
				continue
			randb = _get_root_branch(v)
			if randb not in branches.keys():
				branches[ randb ] = []
			branches[ randb ].append(v)

		all_version_ranges = []
		for branch_key in branches.keys():
			branch_versions = branches[ branch_key ]
			vers_inv = VersionRange('')
			vers_inv.versions = []

			ver_front = Version("")
			ver_front.ge = Version.NEG_INF
			ver_front.lt = [Version.NEG_INF[0] + 1]
			ver_front.root_version = branch_versions[0].root_version
			ver_front.branch_string = branch_versions[0].branch_string
			ver_back = Version("")
			ver_back.ge = Version.INF
			ver_back.lt = [Version.INF[0] + 1]
			ver_back.root_version = branch_versions[0].root_version
			ver_back.branch_string = branch_versions[0].branch_string

			vers = [ver_front] + branch_versions + [ver_back]
			for i in range(0, len(vers)-1):
				v0 = vers[i]
				v1 = vers[i+1]
				if v0.lt < v1.ge:
					v = Version("")
					v.ge, v.lt = v0.lt, v1.ge
					v.root_version, v.branch_string = v0.root_version, v0.branch_string
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

			all_version_ranges.append(vers_inv)

		if len(all_version_ranges) == 0:
			return VersionRange()
		elif len(all_version_ranges) == 1:
			return all_version_ranges[0]
		else:
			version_range_inv = VersionRange()
			version_range_inv.versions = []
			for vr in all_version_ranges:
				version_range_inv.versions += vr.versions

			return version_range_inv

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

	def get_pruned_versions(self, ver):
		"""
		Returned a pruned version of self where all versions in self.versions
		are in the same branch as the parameter "ver"
		"""
		pruned = copy.deepcopy(self)
		pruned.versions = [v for v in pruned.versions if v.same_branch(ver)]
		return pruned

	def get_concrete_versions(self):
		"""
		Returned a pruned version of self where all versions in self.versions
		are in the same branch as the parameter "ver"
		"""
		concrete = copy.deepcopy(self)
		concrete.versions = [v for v in concrete.versions if v.is_concrete()]
		return concrete

	def __str__(self):
		return "|".join(str(v) for v in self.versions)

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
		return copy.deepcopy(versions)
	elif nvers == 2:
		return versions[0].get_union(versions[1])
	else:
		new_versions = []
		idx = 1
		versions_tmp = copy.deepcopy(versions)
		for ver1 in versions_tmp:
			overlap = False
			for ver2 in versions_tmp[idx:]:
				ver_union = ver1.get_union(ver2)
				if len(ver_union) == 1:
					ver2.ge, ver2.lt = ver_union[0].ge, ver_union[0].lt
					ver2.branch_string, ver2.root_version = ver_union[0].branch_string, ver_union[0].root_version
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
