"""
rez-config

rez is a tool for managing package configuration.

'package': a unit of software, or configuration information, which is
installed under a common base path, and may be available as several
variants. A specific version of software is regarded as a package - ie,
'boost' is not a package, but 'boost-1.36' is.

'package family': label for a family of versioned packages. 'boost' is a
package family, whereas 'boost-1.36' is a package.

'package base path': The path under which all variants of a package are
installed. For example, boost-1.36 and its variants might be found under
'/server/boost/1.36/'.

NOTES
---------
'Dependency transitivity' is the assumption that if a package A has a dependent
package B, then an earlier versioned A will have a dependency on an equal or
earlier version of B. For example, given the relationship:
A-3.5 dependsOn B-6.4
then we assume that:
A-3.4 dependsOn B-<=6.4

It follows that we also assume that a later version of A will have a dependency
on an equal or later version of B:
A-3.5 dependsOn B-6.4
then we assume that:
A-3.6 dependsOb B->=6.4

Examples of cases where this assumption is wrong are:
let:
A-3.5 dependsOn B-6.4
then the following cases break the assumption:
'A-3.4 dependsOn B-7.0'
'A-3.4 dependsOn B' (since 'B' is the superset of all versions of B)
'A-3.4 NOT dependsOn B'
"""

import os
import time
import yaml
import copy
import sys
import random
from versions import *
from public_enums import *
from rez_exceptions import *
from rez_metafile import *
from filesys import *

# yes this mirrors rctxt.time_epoch, clean up in V2
g_time_epoch = 0


##############################################################################
# Public Classes
##############################################################################

class PackageRequest:
	"""
	A request for a package. 'version' may be inexact (for eg '5.4+'). If mode
	is != NONE then the request will immediately attempt to resolve itself.

	If the package name starts with '!', then this is an ANTI-package request -
	ie, a requirement that this package, in this version range, is not allowed.
	This feature exists so that packages can describe conflicts with other packages,
	that can't be described by conflicting dependencies.

	If the package name starts with '~' then this is a WEAK package request. It
	means, "I don't need this package, but if it exists then it must fall within
	this version range." A weak request is actually converted to a normal anti-
	package: eg, "~foo-1.3" is equivalent to "!foo-0+<1.3|1.4+".
	"""
	def __init__(self, name, version, mode=RESOLVE_MODE_NONE, time_epoch=0):
		self.name = name

		if self.is_weak():
			# convert into an anti-package
			vr = VersionRange(version)
			vr_inv = vr.get_inverse();
			version = str(vr_inv)
			self.name = '!' + self.name[1:]

		if (mode != RESOLVE_MODE_NONE):
			# goto filesystem and resolve version immediately
			name_ = self.name
			if self.is_anti():
				name_ = name[1:]
			found_path, found_ver = find_package2(syspaths, name_, VersionRange(version), mode, time_epoch)
			if found_ver:
				self.version = str(found_ver)
			else:
				raise PkgsUnresolvedError( [ PackageRequest(name, version) ] )
		else:
			self.version = version

	def is_anti(self):
		return (self.name[0] == '!')

	def is_weak(self):
		return (self.name[0] == '~')

	def short_name(self):
		if (len(self.version) == 0):
			return self.name
		else:
			return self.name + '-' + self.version

	def __str__(self):
		return str((self.name, self.version))


class PackageConflict:
	"""A package conflict. This can occur between a package (possibly a specific
	variant) and a package request
	"""
	def __init__(self, pkg_req_conflicting, pkg_req, variant = None ):
		self.pkg_req = pkg_req
		self.pkg_req_conflicting = pkg_req_conflicting
		self.variant = variant

	def __str__(self):
		tmpstr = str(self.pkg_req)
		if self.variant:
			tmpstr += " variant:" + str(self.variant)
		tmpstr += " <--!--> " + str(self.pkg_req_conflicting)
		return tmpstr


class ResolvedPackage:
	"""
	A resolved package
	"""
	def __init__(self, name, version, base, root, commands, metadata):
		self.name = name
		self.version = version
		self.base = base
		self.root = root
		self.commands = commands
		self.metadata = metadata # original yaml data

	def short_name(self):
		if (len(self.version) == 0):
			return self.name
		else:
			return self.name + '-' + str(self.version)

	def __str__(self):
		return str([self.name, self.version, self.root])


##############################################################################
# Public Functions
##############################################################################

def resolve_packages(pkg_reqs, resolve_mode, quiet = False, verbosity = 0, max_fails = -1, \
	time_epoch = 0, no_path_append = False, build_requires = False, assume_dt = False, \
	is_wrapper = False, meta_vars = None):
	"""
	Given a list of packages, return:
	(a) a list of ResolvedPackage objects, representing the resolved config;
	(b) a list of commands which, when run, should configure the environment;
	(c) a dot-graph representation of the config resolution, as a string;
	(d) the number of failed config attempts before the successful one was found
	-OR-
	raise the relevant exception, if config resolution is not possible

	Inputs:
	pkg_reqs: list of packages to resolve into a configuration
	resolve_mode: one of: RESOLVE_MODE_EARLIEST, RESOLVE_MODE_LATEST
	quiet: if True then hides unnecessary output (such as the progress dots)
	verbosity: print extra debugging info. One of: 0, 1, 2
	max_fails: return after N failed configuration attempts, default -1 (no limit)
	time_epoch: ignore packages newer than this time-date. Default = 0 which is a special
	case, meaning do not ignore any packages
	no_path_append: don't append OS-specific paths to PATH when printing an environment
	assume_dt: Assume dependency transitivity
	is_wrapper: If this env is being resolved for a wrapper, then some very slight changes
	are needed to a normal env, so that wrappers can see one another.
	meta_vars: A list of 2-tuples. [0] is the name of a key; if that key is found in a package
	yaml file, then its value will be baked into the env-var REZ_META_<KEY>. [1] is the
	separator that wil be used, if the value in the yaml is a list.
	"""
	if (len(pkg_reqs) == 0):
		return [], [], "digraph g{}", 0

	if (time_epoch == 0):
		time_epoch = int(time.mktime(time.localtime()))

	g_time_epoch = time_epoch

	rctxt = _ResolvingContext()
	rctxt.resolve_mode = resolve_mode
	rctxt.verbosity = verbosity
	rctxt.max_fails = max_fails
	rctxt.quiet = quiet
	rctxt.time_epoch = time_epoch
	rctxt.build_requires = build_requires
	rctxt.assume_dt = assume_dt

	config = _Configuration()

	for pkg_req in pkg_reqs:
		normalise_pkg_req(pkg_req)
		config.add_package(rctxt, pkg_req)

	for pkg_req in pkg_reqs:
		name = pkg_req.short_name()
		if name.startswith("__wrapper_"):
			name2 = name.replace("__wrapper_", "")
			config.add_dot_graph_verbatim('"' + name +
				'" [label="%s" style="filled" shape=folder fillcolor="rosybrown1"] ;' \
				% (name2))
		else:
			config.add_dot_graph_verbatim('"' + name +
				'" [style=filled shape=box fillcolor="rosybrown1"] ;')

	if (rctxt.verbosity != 0):
		print
		print "initial config:"
	if (rctxt.verbosity == 1):
		print str(config)
	elif (rctxt.verbosity == 2):
		config.dump()


	######################################################
	# do the config resolve - all the action happens here!
	######################################################
	pkg_res_list = config.resolve_packages(rctxt)


	# color resolved packages
	for pkg_res in pkg_res_list:
		config.add_dot_graph_verbatim('"' + pkg_res.short_name() + '" [style=filled fillcolor="darkseagreen1"] ;')

	if (rctxt.verbosity != 0):
		print
		print "final config:"
	if (rctxt.verbosity == 1):
		print str(config)
		print
	elif (rctxt.verbosity == 2):
		config.dump()
		print

	# build the dot-graph representation
	dot_graph = config.get_dot_graph_as_string()

	res_pkg_strs = []
	for pkg_res in pkg_res_list:
		res_pkg_strs.append(pkg_res.short_name())

	# build the environment commands
	env_cmds = []

	# special case env-vars
	env_cmds.append("export PATH=")
	env_cmds.append("export PYTHONPATH=%s/python" % os.getenv("REZ_PATH"))
	if not is_wrapper:
		env_cmds.append("export REZ_WRAPPER_PATH=")

	# this is because of toolchains. They set this env-var. We want it to be overwritten,
	# otherwise we don't get the resolve list of the chain itself - this is why we set it
	# here, before the package commands are written.
	env_cmds.append("export REZ_RESOLVE='"+ str(" ").join(res_pkg_strs)+"'")

	# packages: base/root/version, and commands
	meta_envvars = {}

	for pkg_res in pkg_res_list:
		prefix = "REZ_" + pkg_res.name.upper()
		env_cmds.append("export " + prefix + "_VERSION=" + pkg_res.version)
		env_cmds.append("export " + prefix + "_BASE=" + pkg_res.base)
		env_cmds.append("export " + prefix + "_ROOT=" + pkg_res.root)

		for key,seperator in meta_vars:
			if key in pkg_res.metadata.metadict:
				val = pkg_res.metadata.metadict[key]
				if type(val) == list:
					val = seperator.join(val)
				if key not in meta_envvars:
					meta_envvars[key] = []
				meta_envvars[key].append(pkg_res.name + ':' + val)

		if pkg_res.commands:
			for cmd in pkg_res.commands:
				env_cmds.append([cmd, pkg_res.short_name()])

	for k,v in meta_envvars.iteritems():
		env_cmds.append("export REZ_META_" + k.upper() + "='" + str(' ').join(v) + "'")

	# metadata env-vars (REZ_CONFIG_XXX)
	if (resolve_mode == RESOLVE_MODE_LATEST):
		mode_str = "latest"
	elif (resolve_mode == RESOLVE_MODE_EARLIEST):
		mode_str = "earliest"
	else:
		mode_str = "none"
	env_cmds.append("export REZ_RESOLVE_MODE=" + mode_str)

	req_pkg_strs = []
	for pkg_req in pkg_reqs:
		req_pkg_strs.append(pkg_req.short_name())

	full_req_str = str(' ').join(req_pkg_strs)

	env_cmds.append("export REZ_USED=" + str(os.getenv("REZ_PATH")))
	env_cmds.append("export REZ_REQUEST='" + full_req_str + "'")
	env_cmds.append("export REZ_RAW_REQUEST='" + full_req_str + "'")
	env_cmds.append("export REZ_FAILED_ATTEMPTS=" + str(len(rctxt.config_fail_list)) )
	env_cmds.append("export REZ_REQUEST_TIME=" + str(time_epoch))

	if not no_path_append:
		env_cmds.append("export PATH=$PATH:/bin:/usr/bin:"+os.environ["REZ_PATH"]+"/bin")

	# process the commands
	env_cmds = process_commands(env_cmds)

	if is_wrapper:
		env_cmds.append("export PATH=$PATH:$REZ_WRAPPER_PATH")

	# we're done
	return pkg_res_list, env_cmds, dot_graph, len(rctxt.config_fail_list)



def str_to_pkg_req(str_, time_epoch=0):
	"""
	Helper function: turns a package string (eg 'boost-1.36') into a PackageRequest.
	Note that a version string ending in '=e','=l' will result in a package request
	that immediately resolves to earliest/latest version.
	"""
	mode = RESOLVE_MODE_NONE
	if str_.endswith("=e"):
		mode = RESOLVE_MODE_EARLIEST
	elif str_.endswith("=l"):
		mode = RESOLVE_MODE_LATEST
	if (mode != RESOLVE_MODE_NONE):
		str_ = str_.split('=')[0]

	strs = str_.split('-', 1)
	dim = len(strs)
	if (dim == 1):
		return PackageRequest(str_, "", mode, time_epoch)
	elif (dim == 2):
		return PackageRequest(strs[0], strs[1], mode, time_epoch)
	else:
		raise PkgSystemError("Invalid package string '" + str_ + "'")



def get_base_path(pkg_str):
	if pkg_str.endswith("=l"):
		mode = RESOLVE_MODE_LATEST
		pkg_str = pkg_str[0:-2]
	elif pkg_str.endswith("=e"):
		mode = RESOLVE_MODE_EARLIEST
		pkg_str = pkg_str[0:-2]
	else:
		mode = RESOLVE_MODE_LATEST

	pkg_str = pkg_str.rsplit("=",1)[0]
	strs = pkg_str.split('-', 1)
	name = strs[0]
	if len(strs) == 1:
		verrange = ""
	else:
		verrange = strs[1]

	path, ver = find_package2(syspaths, name, VersionRange(verrange), mode)
	if (not path) or (not ver):
		raise PkgNotFoundError(pkg_str)

	verstr = str(ver)
	if len(verstr) > 0:
		return path + '/' + verstr
	else:
		return path



def make_random_color_string():
	cols = []
	cols.append(random.randint(0,255))
	cols.append(random.randint(0,255))
	cols.append(random.randint(0,255))
	if(cols[0]+cols[1]+cols[2] > 400):
		cols[random.randint(0,2)] = random.randint(0,100)
	s = "#"
	for c in cols:
		h = hex(c)[2:]
		if len(h) == 1:
			h = '0' + h
		s = s + h
	return s


##############################################################################
# Internal Classes
##############################################################################


class _ResolvingContext:
	"""
	Resolving context
	"""
	def __init__(self):
		self.resolve_mode = RESOLVE_MODE_NONE
		self.verbosity = 0
		self.max_fails = -1
		self.config_fail_list = []
		self.last_fail_dot_graph = None
		self.time_epoch = 0
		self.quiet = False
		self.build_requires = False
		self.assume_dt = False


class _PackageVariant:
	"""
	A package variant. The 'working list' member is a list of dependencies that are
	removed during config resolution - a variant with an empty working_list is fully
	resolved. This class has been written with foward compatibility in mind - currently
	a variant is just a list of dependencies, but it may later become a dict, with
	more info than just dependencies.
	"""
	def __init__(self, metadata_node):
		self.metadata = metadata_node
		if (type(self.metadata) == type([])):
			self.working_list = self.metadata[:]
		else:
			raise PkgSystemError("malformed variant metadata: " + str(self.metadata))

	def __str__(self):
		return str(self.metadata)


class _Package:
	"""
	Internal package representation
	"""
	def __init__(self, pkg_req):
		self.is_transitivity = False
		self.has_added_transitivity = False
		if pkg_req:
			self.name = pkg_req.name
			self.version_range = VersionRange(pkg_req.version)
			self.base_path = None
			self.metadata = None
			self.variants = None
			self.root_path = None

			if not self.is_anti():
				# family dir must exist
				family_found = False
				for syspath in syspaths:
					if dir_exists(syspath + '/' + self.name):
						family_found = True
						break

				if not family_found:
					raise PkgFamilyNotFoundError(self.name)

	def __deepcopy__(self, memo_dict):
		"""
		Return a copy of this package. Note that the metadata is not copied. This is the
		exception - metadata is read-only and can be shared between packages.
		"""
		p = _Package(None)
		p.is_transitivity = self.is_transitivity
		p.has_added_transitivity = self.has_added_transitivity
		p.name = self.name
		p.base_path = self.base_path
		p.root_path = self.root_path
		p.version_range = copy.deepcopy(self.version_range, memo_dict)
		p.variants = copy.deepcopy(self.variants, memo_dict)
		p.metadata = self.metadata
		return p

	def get_variants(self):
		"""
		Return package variants, if any
		"""
		return self.variants

	def as_package_request(self):
		"""
		Return this package as a package-request
		"""
		return PackageRequest(self.name, str(self.version_range))

	def is_anti(self):
		"""
		Return True if this is an anti-package
		"""
		return (self.name[0] == '!')

	def short_name(self):
		"""
		Return a short string representation, eg 'boost-1.36'
		"""
		if self.version_range.is_any():
			return self.name
		else:
			return self.name + '-' + str(self.version_range)

		return self.name + '-' + str(self.version_range)

	def is_metafile_resolved(self):
		"""
		Return True if this package has had its metafile resolved
		"""
		return (self.base_path != None)

	def is_resolved(self):
		"""
		Return True if this package has been resolved (ie, there are either no
		variants, or a specific variant has been chosen)
		"""
		return (self.root_path != None)

	def resolve(self, root_path):
		"""
		Resolve this package, ie set its root path

		.. todo::
			 optimisation: just do this right at the end of resolve_packages
		"""
		self.root_path = root_path

	# Get commands with string-replacement
	def get_resolved_commands(self):
		"""
		"""
		if self.is_resolved():
			cmds = self.metadata.get_string_replace_commands(str(self.version_range), self.base_path, self.root_path)
			return cmds
		else:
			return None

	def resolve_metafile(self):
		"""
		attempt to resolve the metafile, the metadata member will be set if
		successful, and True will be returned. If the package has no variants,
		then its root-path is set and this package is regarded as fully-resolved.
		"""
		is_any = self.version_range.is_any()
		if self.version_range.is_inexact() and not is_any:
			return False

		if not self.base_path:
			for syspath in syspaths:
				base_path = syspath + '/' + self.name

				found_ver = find_package(base_path, self.version_range, \
					RESOLVE_MODE_NONE, g_time_epoch)

				if (found_ver != None):

					if not is_any:
						base_path += '/' + str(self.version_range)
					metafile = base_path  + '/' + PKG_METADATA_FILENAME

					self.base_path = base_path
					self.metadata = get_cached_metadata(metafile)
					metafile_variants = self.metadata.get_variants()
					if metafile_variants:
						# convert variants from metafile into _PackageVariants
						self.variants = []
						for metavar in metafile_variants:
							pkg_var = _PackageVariant(metavar)
							self.variants.append(pkg_var)
					else:
						# no variants, we're fully resolved
						self.resolve(self.base_path)
					break

		return (self.base_path != None)

	def __str__(self):
		l = [ self.short_name() ]
		if self.root_path:
			l.append('R' + self.root_path)
		elif self.base_path:
			l.append('B' + self.base_path)
		if(self.is_transitivity):
			l.append('t')

		variants = self.get_variants()
		if (variants):
			vars = []
			for var in variants:
				vars.append(var.working_list)
			l.append("working_vars:" + str(vars))
		return str(l)




class _Configuration:
	"""
	Internal configuration representation
	"""
	s_uid = 0

	def __init__(self, inc_uid = False):
		# packages map, for quick lookup
		self.pkgs = {}
		# packages list, for order retention wrt resolving
		self.families = []
		# connections in a dot graph
		self.dot_graph = []
		# uid
		if inc_uid:
			_Configuration.s_uid += 1
		self.uid = _Configuration.s_uid

	def get_num_packages(self):
		"""
		return number of packages
		"""
		num = 0
		for name,pkg in self.pkgs.iteritems():
			if not pkg.is_anti():
				num += 1
		return num

	def get_num_resolved_packages(self):
		"""
		return number of resolved packages
		"""
		num = 0
		for name,pkg in self.pkgs.iteritems():
			if pkg.is_resolved():
				num += 1
		return num

	def all_resolved(self):
		"""
		returns True if all packages are resolved
		"""
		return (self.get_num_resolved_packages() == self.get_num_packages())

	ADDPKG_CONFLICT 	= 0
	ADDPKG_ADD 			= 1
	ADDPKG_NOEFFECT		= 2

	def test_pkg_req_add(self, pkg_req, create_pkg_add):
		"""
		test the water to see what adding a package request would do to the config. Possible results are:
		(ADDPKG_CONFLICT, pkg_conflicting):
		The package cannot be added because it would conflict with pkg_conflicting
		(ADDPKG_NOEFFECT, None):
		The package doesn't need to be added, there is an identical package already there
		(ADDPKG_ADD, pkg_add):
		The package can be added, and the config updated accordingly by adding pkg_add (replacing
		a package with the same family name if it already exists in the config)

		.. note::
			that if 'create_pkg_add' is False, then 'pkg_add' will always be None.
		"""

		# do a shortcut and test pkg short-names, if they're identical then we can often
		# return 'NOEFFECT'. Sometimes short names can mismatch, but actually be identical,
		# but this is of no real consequence, and testing on short-name is a good optimisation
		# (testing VersionRanges for equality is not trivial)
		pkg_shortname = pkg_req.short_name()

		pkg_req_ver_range = VersionRange(pkg_req.version)

		if pkg_req.is_anti():

			if pkg_req.name[1:] in self.pkgs:
				config_pkg = self.pkgs[pkg_req.name[1:] ]

				# if anti and existing non-anti don't overlap then no effect
				ver_range_intersect = config_pkg.version_range.get_intersection(pkg_req_ver_range)
				if not ver_range_intersect:
					return (_Configuration.ADDPKG_NOEFFECT, None)

				# if (inverse of anti) and non-anti intersect, then reduce existing non-anti,
				# otherwise there is a conflict
				pkg_req_inv_ver_range = pkg_req_ver_range.get_inverse()
				ver_range_intersect = config_pkg.version_range.get_intersection(pkg_req_inv_ver_range)
				if ver_range_intersect:
					pkg_add = None
					if create_pkg_add:
						pkg_add = copy.deepcopy(config_pkg)
						pkg_add.version_range = ver_range_intersect
						return (_Configuration.ADDPKG_ADD, pkg_add)
				else:
					return (_Configuration.ADDPKG_CONFLICT, config_pkg)

			# union with anti if one already exists
			if pkg_req.name in self.pkgs:
				config_pkg = self.pkgs[pkg_req.name]
				if (config_pkg.short_name() == pkg_shortname):
					return (_Configuration.ADDPKG_NOEFFECT, None)

				ver_range_union = config_pkg.version_range.get_union(pkg_req_ver_range)
				pkg_add = None
				if create_pkg_add:
					pkg_add = copy.deepcopy(config_pkg)
					pkg_add.version_range = ver_range_union
				return (_Configuration.ADDPKG_ADD, pkg_add)

		else:

			if ('!' + pkg_req.name) in self.pkgs:
				config_pkg = self.pkgs['!' + pkg_req.name]

				# if non-anti and existing anti don't overlap then pkg can be added
				ver_range_intersect = config_pkg.version_range.get_intersection(pkg_req_ver_range)
				if not ver_range_intersect:
					pkg_add = None
					if create_pkg_add:
						pkg_add = _Package(pkg_req)
					return (_Configuration.ADDPKG_ADD, pkg_add)

				# if non-anti and (inverse of anti) intersect, then add reduced anti,
				# otherwise there is a conflict
				config_pkg_inv_ver_range = config_pkg.version_range.get_inverse()
				ver_range_intersect = config_pkg_inv_ver_range.get_intersection(pkg_req_ver_range)
				if ver_range_intersect:
					pkg_add = None
					if create_pkg_add:
						pkg_add = _Package(pkg_req)
						pkg_add.version_range = ver_range_intersect
						return (_Configuration.ADDPKG_ADD, pkg_add)
				else:
					return (_Configuration.ADDPKG_CONFLICT, config_pkg)

			# intersect with non-anti if one already exists, and conflict if no intersection
			if pkg_req.name in self.pkgs:
				config_pkg = self.pkgs[pkg_req.name]
				if (config_pkg.short_name() == pkg_shortname):
					return (_Configuration.ADDPKG_NOEFFECT, None)

				ver_range_intersect = config_pkg.version_range.get_intersection(pkg_req_ver_range)
				if ver_range_intersect:
					if config_pkg.is_resolved():
						# if there is an intersection, and the package we already have is resolved
						# remove any packages (to add) that are not part of the existing branch. this
						# is because the intersection of a plain version and a branch version will
						# give a overly-specific branch version, so this will weed out undesired
						# versions.
						assert len(config_pkg.version_range.versions)==1
						pruned = ver_range_intersect.get_pruned_versions(config_pkg.version_range.versions[0])
						if pruned.is_none():
							return (_Configuration.ADDPKG_CONFLICT, config_pkg)
					pkg_add = None
					if create_pkg_add:
						pkg_add = copy.deepcopy(config_pkg)
						pkg_add.version_range = ver_range_intersect
					return (_Configuration.ADDPKG_ADD, pkg_add)
				else:
					return (_Configuration.ADDPKG_CONFLICT, config_pkg)

		# package can be added directly, doesn't overlap with anything
		pkg_add = None
		if create_pkg_add:
			pkg_add = _Package(pkg_req)
		return (_Configuration.ADDPKG_ADD, pkg_add)

	def get_conflicting_package(self, pkg_req):
		"""
		return a package in the current configuration that 'pkg' would conflict with, or
		None if no conflict would occur
		"""
		result, pkg_conflict = self.test_pkg_req_add(pkg_req, False)
		if (result == _Configuration.ADDPKG_CONFLICT):
			return pkg_conflict
		else:
			return None

	PKGCONN_REDUCE 		= 0
	PKGCONN_RESOLVE 	= 1
	PKGCONN_REQUIRES 	= 2
	PKGCONN_CONFLICT	= 3
	PKGCONN_VARIANT		= 4
	PKGCONN_CYCLIC		= 5
	PKGCONN_TRANSITIVE	= 6

	def add_package(self, rctxt, pkg_req, parent_pkg = None, dot_connection_type = 0):
		"""
		add a package request to this configuration, optionally describing the 'parent'
		package (ie the package that requires it), and the type of dot-graph connection,
		if the pkg has a parent pkg.
		"""
		if parent_pkg:
			connt = _Configuration.PKGCONN_REQUIRES
			if dot_connection_type == _Configuration.PKGCONN_TRANSITIVE:
				connt = _Configuration.PKGCONN_TRANSITIVE
				self.add_dot_graph_verbatim('"' + pkg_req.short_name() + \
					'" [ shape=octagon ] ;')

			self.dot_graph.append( ( parent_pkg.short_name(), ( pkg_req.short_name(), connt ) ) )

		# test to see what adding this package would do
		result, pkg = self.test_pkg_req_add(pkg_req, True)

		if (result == _Configuration.ADDPKG_CONFLICT):

			self.dot_graph.append( ( pkg.short_name(), ( pkg_req.short_name(), \
				_Configuration.PKGCONN_CONFLICT ) ) )
			rctxt.last_fail_dot_graph = self.get_dot_graph_as_string()

			pkg_conflict = PackageConflict(pkg_to_pkg_req(pkg), pkg_req)
			raise PkgConflictError([ pkg_conflict ], rctxt.last_fail_dot_graph)

		elif (result == _Configuration.ADDPKG_ADD) and (pkg != None):

			# update dot-graph
			pkgname = pkg.short_name()
			if pkg.name in self.pkgs:
				connt = dot_connection_type
				if (connt != _Configuration.PKGCONN_RESOLVE):
					connt = _Configuration.PKGCONN_REDUCE

				pkgname_existing = self.pkgs[pkg.name].short_name()
				# if pkg and pkg-existing have same short-name, then a further-reduced package was already
				# in the config (eg, we added 'python' to a config with 'python-2.5')
				if (pkgname_existing == pkgname):
					self.dot_graph.append( ( pkg_req.short_name(), ( pkgname_existing, connt ) ) )
				else:
					self.dot_graph.append( ( pkgname_existing, ( pkgname, connt ) ) )
			self.dot_graph.append( ( pkgname, None ) )

			if dot_connection_type == _Configuration.PKGCONN_TRANSITIVE:
				pkg.is_transitivity = True

			# add pkg, possibly replacing existing pkg. This is to retain order of package addition,
			# since package resolution is sensitive to this
			if (not pkg.is_anti()) and (not (pkg.name in self.pkgs)):
				self.families.append(pkg.name)
			self.pkgs[pkg.name] = pkg

			# if pkg is non-anti then remove its anti from the config, if it's there. Adding a
			# non-anti pkg to the config without a conflict occurring always means we can safely
			# remove the anti pkg, if it exists.
			if not pkg.is_anti():
				if ('!' + pkg.name) in self.pkgs:
					del self.pkgs['!' + pkg.name]


	def get_dot_graph_as_string(self):
		"""
		return a string-representation of the dot-graph. You should be able to
		write this to file, and view it in a dot viewer, such as dotty or graphviz
		"""
		dotstr = "digraph g { \n"
		conns = set()

		for connection in self.dot_graph:
			if type(connection) == type(""):
				verbatim_txt = connection
				dotstr += verbatim_txt + '\n';
			else:
				if connection not in conns:
					if connection[1]:
						dep, conntype = connection[1]
						dotstr += '"' + connection[0] + '" -> "' + dep + '" '
						if(conntype == _Configuration.PKGCONN_REQUIRES):
							col = make_random_color_string()
							conn_style = '[label=needs color="' + col + '" fontcolor="' + col + '"]'
						elif(conntype == _Configuration.PKGCONN_TRANSITIVE):
							col = make_random_color_string()
							conn_style = '[label=willneed color="' + col + '" fontcolor="' + col + '"]'
						elif(conntype == _Configuration.PKGCONN_RESOLVE):
							conn_style = '[label=resolve color="green4" fontcolor="green4" style="bold"]'
						elif(conntype == _Configuration.PKGCONN_REDUCE):
							conn_style = '[label=reduce color="grey30" fontcolor="grey30" style="dashed"]'
						elif(conntype == _Configuration.PKGCONN_VARIANT):
							conn_style = '[label=variant color="grey30" fontcolor="grey30" style="dashed"]'
						elif(conntype == _Configuration.PKGCONN_CYCLIC):
							conn_style = '[label=CYCLE color="red" fontcolor="red" fontsize="30" style="bold"]'
						else:
							conn_style = '[label=CONFLICT color="red" fontcolor="red" fontsize="30" style="bold"]'
						dotstr += conn_style + ' ;\n'
					else:
						dotstr += '"' + connection[0] + '" ;\n'
					conns.add(connection)

		dotstr += "}\n"
		return dotstr

	def add_dot_graph_verbatim(self, txt):
		"""
		add a verbatim string to the dot-graph output
		"""
		self.dot_graph.append(txt)

	def copy(self):
		"""
		return a shallow copy
		"""
		confcopy = _Configuration()
		confcopy.pkgs = self.pkgs.copy()
		confcopy.families = self.families[:]
		confcopy.dot_graph = self.dot_graph[:]
		return confcopy

	def swap(self, a):
		"""
		swap this config's contents with another
		"""
		self.pkgs, a.pkgs = a.pkgs, self.pkgs
		self.families, a.families = a.families, self.families
		self.dot_graph, a.dot_graph = a.dot_graph, self.dot_graph

	def get_unresolved_packages_as_package_requests(self):
		"""
		return a list of unresolved packages as package requests
		"""
		pkg_reqs = []
		for name,pkg in self.pkgs.iteritems():
			if (not pkg.is_resolved()) and (not pkg.is_anti()):
				pkg_reqs.append(pkg_to_pkg_req(pkg))
		return pkg_reqs

	def get_all_packages_as_package_requests(self):
		"""
		return a list of all packages as package requests
		"""
		pkg_reqs = []
		for name,pkg in self.pkgs.iteritems():
			pkg_reqs.append(pkg_to_pkg_req(pkg))
		return pkg_reqs

	def resolve_packages(self, rctxt):
		"""
		resolve the current configuration - all the action happens here. On success,
		a resolved package list is returned. This function should only fail via an
		exception - if an infinite loop results then there is a bug somewheres.
		Please note that the returned list order is important. Required packages appear
		first, and requirees later... since a package's commands may refer to env-vars set
		in a required package's commands.
		"""

		while (not self.all_resolved()) and \
		    ((rctxt.max_fails == -1) or (len(rctxt.config_fail_list) <= rctxt.max_fails)):

			# do an initial resolve pass
			self.resolve_packages_no_filesys(rctxt)
			if self.all_resolved():
				break

			# fail if not all resolved and mode=none
			if (not self.all_resolved()) and (rctxt.resolve_mode == RESOLVE_MODE_NONE):
				pkg_reqs = self.get_unresolved_packages_as_package_requests()
				raise PkgsUnresolvedError(pkg_reqs)

			# add transitive dependencies
			self.add_transitive_dependencies(rctxt)

			# this shouldn't happen here but just in case...
			if self.all_resolved():
				break

			# find first package with unresolved metafile. Note that self.families exists in
			# order to retain package order, because different package order can result
			# in different configuration resolution.
			pkg = None
			for name in self.families:
				pkg_ = self.pkgs[name]
				if not pkg_.is_metafile_resolved():
					pkg = pkg_
					break

			if not pkg:
				# The remaining unresolved packages must have more than one variant each. So
				# find that variant, out of all remaining packages, that is 'least suitable',
				# and remove it. 'least suitable' means that the variant has largest number
				# of packages that do not intersect with anything in the config.
				if (rctxt.verbosity != 0):
					print
					print "Ran out of concrete resolution choices, yet unresolved packages still remain:"
					if (rctxt.verbosity == 1):
						print str(self)
					elif (rctxt.verbosity == 2):
						self.dump()

				self.remove_least_suitable_variant(rctxt)

			else:

				ver_range_valid = pkg.version_range
				valid_config_found = False

				# attempt to resolve a copy of the current config with this package resolved
				# as closely as possible to desired (eg in mode=latest, start with latest and
				# work down). The first config to resolve represents the most desirable. Note
				# that resolve_packages will be called recursively
				num_version_searches = 0
				while (not (ver_range_valid == None)) and \
		            ((rctxt.max_fails == -1) or (len(rctxt.config_fail_list) <= rctxt.max_fails)):

					num_version_searches += 1

					# resolve package to as closely desired as possible
					try:
						pkg_req_ = PackageRequest(pkg.name, str(ver_range_valid), rctxt.resolve_mode, rctxt.time_epoch)
					except PkgsUnresolvedError, e:

						if(num_version_searches == 1):
							# this means that rather than running out of versions of this lib to try, there
							# were never any versions found at all - which means this package doesn't exist
							self.add_dot_graph_verbatim('"' + \
								e.pkg_reqs[0].short_name() + ' NOT FOUND' + \
								'" [style=filled fillcolor="orangered"] ;')
							self.add_dot_graph_verbatim('"' + \
								e.pkg_reqs[0].short_name() + '" -> "' + \
								e.pkg_reqs[0].short_name() + ' NOT FOUND" ;')
							rctxt.last_fail_dot_graph = self.get_dot_graph_as_string()

							sys.stderr.write("Warning! Package not found: " + str(e.pkg_reqs[0]) + "\n")
							raise PkgNotFoundError(e.pkg_reqs[0])

						if (self.uid == 0):
							# we're the topmost configuration, and there are no more packages to try -
							# all possible configuration attempts have failed at this point
							break
						else:
							raise e

					pkg_resolve_str = pkg.short_name() + " --> " + pkg_req_.short_name()

					# restrict next package search to one version less desirable
					try:
						if (rctxt.resolve_mode == RESOLVE_MODE_LATEST):
							ver_range_valid = ver_range_valid.get_intersection(VersionRange("0+<" + pkg_req_.version))
						else:
							ver_inc = Version(pkg_req_.version).get_inc()
							ver_range_valid = ver_range_valid.get_intersection(VersionRange(str(ver_inc) + '+'))
					except VersionError:
						ver_range_valid = None

					# create config copy, bit of fiddling though cause we want a proper guid
					config2 =_Configuration(True)
					guid_ = config2.uid

					# todo optimisation here, a full deep copy isn't necessary - probably pkgs need
					# copies, but their metadata could remain shared with pkg copy. Since metadata will
					# become large for some packages, this is worth doing. So, impl Config.deepcopy().
					config2 = copy.deepcopy(self)
					config2.uid = guid_

					if (rctxt.verbosity != 0):
						print
						print "SPAWNED NEW CONFIG #" + str(config2.uid) + " FROM PARENT #" + str(self.uid) + \
							" BASED ON FILESYS RESOLUTION: " + pkg_resolve_str

					# attempt to add package to config copy
					try:
						config2.add_package(rctxt, pkg_req_, None, _Configuration.PKGCONN_RESOLVE)
					except PkgConflictError, e:
						rctxt.last_fail_dot_graph = config2.get_dot_graph_as_string()

						if (rctxt.verbosity != 0):
							print
							print "CONFIG #" + str(config2.uid) + " FAILED (" + e.__class__.__name__ + "):"
							print str(e)
							print
							print "ROLLING BACK TO CONFIG #" + self.uid
						continue

					if (rctxt.verbosity != 0):
						print
						print "config after applying: " + pkg_resolve_str
						if (rctxt.verbosity == 1):
							print str(config2)
						elif (rctxt.verbosity == 2):
							config2.dump()

					# now fully resolve config copy
					try:
						config2.resolve_packages(rctxt)
					except ( \
						PkgConfigNotResolvedError, \
						PkgsUnresolvedError, \
						PkgConflictError, \
						PkgNotFoundError, \
						PkgFamilyNotFoundError, \
						PkgSystemError), e:

						# store fail reason into list, unless it's a PkgConfigNotResolvedError - this error just
						# tells us that the sub-config failed because its sub-config failed.
						if (type(e) not in [PkgConfigNotResolvedError, PkgsUnresolvedError]):

							sys.stderr.write("conflict " + str(len(rctxt.config_fail_list)) + ": " + config2.short_str() + '\n')
							sys.stderr.flush()

							this_fail = "config: (" + str(config2).strip() + "): " + \
								e.__class__.__name__ + ": " + str(e)

							if(rctxt.max_fails >= 0):
								if(len(rctxt.config_fail_list) <= rctxt.max_fails):
									rctxt.config_fail_list.append(this_fail)
									if(len(rctxt.config_fail_list) > rctxt.max_fails):
										rctxt.config_fail_list.append("Maximum configuration failures reached.")
										pkg_reqs_ = self.get_all_packages_as_package_requests()
										raise PkgConfigNotResolvedError(pkg_reqs_, \
											rctxt.config_fail_list, rctxt.last_fail_dot_graph)
							else:
								rctxt.config_fail_list.append(this_fail)

						if (rctxt.verbosity != 0):
							print
							print "CONFIG #" + str(config2.uid) + " FAILED (" + e.__class__.__name__ + "):"
							print str(e)
							print
							print "ROLLING BACK TO CONFIG #" + str(self.uid)

						continue

					# if we got here then we have a valid config yay!
					self.swap(config2)
					valid_config_found = True
					break

				if not valid_config_found:
					# we're exhausted the possible versions of this package to try
					fail_msg = "No more versions to be found on filesys: " + pkg.short_name()
					if (rctxt.verbosity != 0):
						print
						print fail_msg

					pkg_reqs_ = self.get_all_packages_as_package_requests()
					raise PkgConfigNotResolvedError(pkg_reqs_, \
						rctxt.config_fail_list, rctxt.last_fail_dot_graph)

		#################################################
		# woohoo, we have a fully resolved configuration!
		#################################################

		# check for cyclic dependencies
		cyclic_deps = self.detect_cyclic_dependencies()
		if len(cyclic_deps) > 0:
			# highlight cycles in the dot-graph
			for pkg1, pkg2 in cyclic_deps:
				self.dot_graph.append( ( pkg1, ( pkg2, _Configuration.PKGCONN_CYCLIC ) ) )

			dot_str = self.get_dot_graph_as_string()
			raise PkgCyclicDependency(cyclic_deps, dot_str)

		# convert packages into a list of package resolutions, forcing them into the correct order wrt command sourcing
		ordered_fams = self.get_ordered_families()

		pkg_ress = []
		for name in ordered_fams:
			pkg = self.pkgs[name]
			if not pkg.is_anti():
				resolved_cmds = pkg.get_resolved_commands()
				pkg_res = ResolvedPackage(name, str(pkg.version_range), pkg.base_path, \
                    pkg.root_path, resolved_cmds, pkg.metadata)
				pkg_ress.append(pkg_res)

		return pkg_ress

	def _create_family_dependency_tree(self):
		"""
		From the dot-graph, extract a dependency tree containing unversioned pkgs (ie families),
		and a set of all existing families
		"""
		deps = set()
		fams = set()
		for conn in self.dot_graph:
			if (type(conn) != type("")) and \
				(conn[0][0] != '!'):
				fam1 = conn[0].split('-',1)[0]
				fams.add(fam1)
				if (conn[1] != None) and \
					(conn[1][1] == _Configuration.PKGCONN_REQUIRES) and \
					(conn[1][0][0] != '!'):
					fam2 = conn[1][0].split('-',1)[0]
					fams.add(fam2)
					if fam1 != fam2:
						deps.add( (fam1, fam2) )

		return deps, fams

	def get_ordered_families(self):
		"""
		Return the families of all packages in such an order that required packages appear
		before requirees. This means we can properly order package command construction -
		if A requires B, then A's commands might refer to an env-var set in B's commands.
		"""
		fam_list = []
		deps, fams = self._create_family_dependency_tree()

		while len(deps) > 0:
			parents = set()
			children = set()
			for dep in deps:
				parents.add(dep[0])
				children.add(dep[1])

			leaf_fams = children - parents
			if len(leaf_fams) == 0:
				break 	# if we hit this then there are cycle(s) somewhere

			for fam in leaf_fams:
				fam_list.append(fam)

			del_deps = set()
			for dep in deps:
				if dep[1] in leaf_fams:
					del_deps.add(dep)
			deps -= del_deps

			fams -= leaf_fams

		# anything left in the fam set is a topmost node
		for fam in fams:
			fam_list.append(fam)

		return fam_list


	def detect_cyclic_dependencies(self):
		"""
		detect cyclic dependencies, if they exist
		"""
		# extract dependency tree from dot-graph
		deps = self._create_family_dependency_tree()[0]

		# remove leaf nodes
		while len(deps) > 0:
			parents = set()
			children = set()
			for dep in deps:
				parents.add(dep[0])
				children.add(dep[1])

			leaf_fams = children - parents
			if len(leaf_fams) == 0:
				break

			del_deps = set()
			for dep in deps:
				if dep[1] in leaf_fams:
					del_deps.add(dep)
			deps -= del_deps

		# remove topmost nodes
		while len(deps) > 0:
			parents = set()
			children = set()
			for dep in deps:
				parents.add(dep[0])
				children.add(dep[1])

			top_fams = parents - children
			if len(top_fams) == 0:
				break

			del_deps = set()
			for dep in deps:
				if dep[0] in top_fams:
					del_deps.add(dep)
			deps -= del_deps

		# anything left is part of a cyclic loop...

		if len(deps) > 0:
			# inject pkg versions into deps list
			deps2 = set()
			for dep in deps:
				pkg1 = self.pkgs[ dep[0] ].short_name()
				pkg2 = self.pkgs[ dep[1] ].short_name()
				deps2.add( (pkg1, pkg2) )
			deps = deps2

		return deps

	def resolve_packages_no_filesys(self, rctxt):
		"""
		resolve current packages as far as possible without querying the file system
		"""

		nresolved_metafiles = -1
		nresolved_common_variant_pkgs = -1
		nconflicting_variants_removed = -1
		nresolved_single_variant_pkgs = -1

		while ((( \
				nresolved_metafiles + \
				nresolved_common_variant_pkgs + \
				nconflicting_variants_removed + \
				nresolved_single_variant_pkgs) != 0) and
				(not self.all_resolved())):

			# resolve metafiles
			nresolved_metafiles = self.resolve_metafiles(rctxt)

			# remove conflicting variants
			nconflicting_variants_removed = self.remove_conflicting_variants(rctxt)

			# resolve common variant packages
			nresolved_common_variant_pkgs = self.resolve_common_variants(rctxt)

			# resolve packages with a single, fully-resolved variant
			nresolved_single_variant_pkgs = self.resolve_single_variant_packages(rctxt)

	def remove_least_suitable_variant(self, rctxt):
		"""
		remove one variant from any remaining unresolved packages, such that that variant is
		'least suitable' - that is, has the greatest number of packages which do not appear
		in the current configuration
		TODO remove this I think, error instead
		"""

		bad_pkg = None
		bad_variant = None
		bad_variant_score = -1

		for name,pkg in self.pkgs.iteritems():
			if (not pkg.is_resolved()) and (not pkg.is_anti()):
				for variant in pkg.get_variants():
					sc = self.get_num_unknown_pkgs(variant.working_list)
					if (sc > bad_variant_score):
						bad_pkg = pkg
						bad_variant = variant
						bad_variant_score = sc

		bad_pkg.get_variants().remove(bad_variant)

		if (rctxt.verbosity != 0):
			print
			print "removed least suitable variant:"
			print bad_pkg.short_name() + " variant:" + str(bad_variant)

	def get_num_unknown_pkgs(self, pkg_strs):
		"""
		given a list of package strings, return the number of packages in the list
		which do not appear in the current configuration
		"""
		num = 0
		for pkg_str in pkg_strs:
			pkg_req = str_to_pkg_req(pkg_str)
			if pkg_req.name not in self.pkgs:
				num += 1

		return num

	def resolve_metafiles(self, rctxt):
		"""
		for each package, resolve metafiles until no more can be resolved, returning
		the number of metafiles that were resolved.
		"""

		num = 0
		config2 = self.copy()

		for name, pkg in self.pkgs.iteritems():
			if (pkg.metadata == None):
				if pkg.resolve_metafile():
					num += 1

					if (rctxt.verbosity != 0):
						print
						print "resolved metafile for " + pkg.short_name() + ":"
					if (rctxt.verbosity == 1):
						print str(config2)
					elif (rctxt.verbosity == 2):
						print str(pkg)

					# add required packages to the configuration, this may
					# reduce wrt existing packages (eg: foo-1 -> foo-1.2 is a reduction)
					requires = pkg.metadata.get_requires(rctxt.build_requires)

					if requires:
						for pkg_str in requires:
							pkg_req = str_to_pkg_req(pkg_str, rctxt.time_epoch)

							if (rctxt.verbosity != 0):
								print
								print "adding " + pkg.short_name() + \
									"'s required package " + pkg_req.short_name() + '...'

							config2.add_package(rctxt, pkg_req, pkg)

							if (rctxt.verbosity != 0):
								print "config after adding " + pkg.short_name() + \
									"'s required package " + pkg_req.short_name() + ':'
							if (rctxt.verbosity == 1):
								print str(config2)
							elif (rctxt.verbosity == 2):
								config2.dump()

		if num>0:
			self.swap(config2)
		return num


	def add_transitive_dependencies(self, rctxt):
		"""
		for each package that is inexact and not resolved, calculate the package ranges that
		it must eventually pull in anyway, assuming dependency transitivity, and add those to
		the current configuration.
		"""
		if not rctxt.assume_dt:
			return
		while (self._add_transitive_dependencies(rctxt) > 0):
			pass


	def _add_transitive_dependencies(self, rctxt):

		num = 0
		config2 = self.copy()

		for name, pkg in self.pkgs.iteritems():
			if pkg.is_metafile_resolved():
				continue
			if pkg.is_anti():
				continue
			if pkg.has_added_transitivity:
				continue

			# get the requires lists for the earliest and latest versions of this pkg
			found_path, found_ver = find_package2(syspaths, pkg.name, pkg.version_range, \
				RESOLVE_MODE_EARLIEST, rctxt.time_epoch)
			if (not found_path) or (not found_ver):
				continue
			metafile_e = get_cached_metadata(found_path + "/" + str(found_ver) + "/package.yaml")
			if not metafile_e:
				continue

			found_path, found_ver = find_package2(syspaths, pkg.name, pkg.version_range, \
				RESOLVE_MODE_LATEST, rctxt.time_epoch)
			if (not found_path) or (not found_ver):
				continue
			metafile_l = get_cached_metadata(found_path + "/" + str(found_ver) + "/package.yaml")
			if not metafile_l:
				continue

			pkg.has_added_transitivity = True

			requires_e = metafile_e.get_requires()
			requires_l = metafile_l.get_requires()
			if (not requires_e) or (not requires_l):
				continue

			# find pkgs that exist in the requires of both, and add these to the current
			# config as 'transitivity' packages
			for pkg_str_e in requires_e:
				if (pkg_str_e[0] == '!') or (pkg_str_e[0] == '~'):
					continue

				pkg_req_e = str_to_pkg_req(pkg_str_e, rctxt.time_epoch)

				for pkg_str_l in requires_l:
					pkg_req_l = str_to_pkg_req(pkg_str_l, rctxt.time_epoch)
					if (pkg_req_e.name == pkg_req_l.name):
						pkg_req = pkg_req_e
						if (pkg_req_e.version != pkg_req_l.version):
							# calc version range
							v_e = Version(pkg_req_e.version)
							v_l = Version(pkg_req_l.version)
							if(not v_e.ge < v_l.lt):
								continue
							v = Version()
							v.ge = v_e.ge
							v.lt = v_l.lt
							if (v.ge == Version.NEG_INF) and (v.lt != Version.INF):
								v.ge = [0]
							pkg_req = PackageRequest(pkg_req_e.name, str(v))

						config2.add_package(rctxt, pkg_req, pkg, _Configuration.PKGCONN_TRANSITIVE)
						num = num + 1

			# find common variants that exist in both. Note that this code is somewhat redundant,
			# v similar work is done in resolve_common_variants - fix this in rez V2
			variants_e = metafile_e.get_variants()
			variants_l = metafile_l.get_variants()
			if (not variants_e) or (not variants_l):
				continue

			common_pkg_fams = None
			pkg_vers = {}

			for variant in (variants_e + variants_l):
				comm_fams = set()
				for pkgstr in variant:
					pkgreq = str_to_pkg_req(pkgstr, rctxt.time_epoch)
					comm_fams.add(pkgreq.name)
					if pkgreq.name in pkg_vers:
						pkg_vers[pkgreq.name].append(pkgreq.version)
					else:
						pkg_vers[pkgreq.name] = [ pkgreq.version ]

				if (common_pkg_fams == None):
					common_pkg_fams = comm_fams
				else:
					common_pkg_fams &= comm_fams

				if len(common_pkg_fams) == 0:
					break

			if (common_pkg_fams != None):
				for pkg_fam in common_pkg_fams:
					ver_range = VersionRange(str("|").join(pkg_vers[pkg_fam]))
					v = Version()
					if len(ver_range.versions) > 0:
						v.ge = ver_range.versions[0].ge
						v.lt = ver_range.versions[-1].lt
						if (v.ge == Version.NEG_INF) and (v.lt != Version.INF):
							v.ge = [0]

						pkg_req = PackageRequest(pkg_fam, str(v))
						config2.add_package(rctxt, pkg_req, pkg, _Configuration.PKGCONN_TRANSITIVE)
						num = num + 1

		if num>0:
			self.swap(config2)
		return num


	def remove_conflicting_variants(self, rctxt):
		"""
		for each package, remove those variants which contain one or more packages which
		conflict with the current configuration. If a package has all of its variants
		removed in this way, then a pkg-conflict exception will be raised.
		"""

		if (rctxt.verbosity == 2):
			print
			print "removing conflicting variants..."

		num = 0

		for name,pkg in self.pkgs.iteritems():

			variants = pkg.get_variants()
			if variants != None:
				conflicts = []

				conflicting_variants = set()
				for variant in variants:
					for pkgstr in variant.metadata:
						pkg_req_ = str_to_pkg_req(pkgstr, rctxt.time_epoch)
						pkg_conflicting = self.get_conflicting_package(pkg_req_)
						if pkg_conflicting:
							pkg_req_conflicting = pkg_conflicting.as_package_request()
							pkg_req_this = pkg.as_package_request()
							pc = PackageConflict(pkg_req_conflicting, pkg_req_this, variant.metadata)
							conflicts.append(pc)
							conflicting_variants.add(variant)
							num += 1
							break

				if (len(conflicts) > 0):
					if (len(conflicts) == len(variants)):	# all variants conflict

						self.add_dot_graph_verbatim(\
							'subgraph cluster_variants {\n' + \
							'style=filled ;\n' + \
							'label=variants ;\n' + \
							'fillcolor="lightcyan1" ;' )

						# show all variants and conflicts in dot-graph
						for variant in variants:
							varstr = str(", ").join(variant.metadata)
							self.add_dot_graph_verbatim('"' + varstr + '" [style=filled fillcolor="white"] ;')

						self.add_dot_graph_verbatim('}')

						for variant in variants:
							varstr = str(", ").join(variant.metadata)
							self.dot_graph.append( ( pkg_req_this.short_name(), \
								( varstr, _Configuration.PKGCONN_VARIANT ) ) )
							self.dot_graph.append( ( pkg_req_conflicting.short_name(), \
								( varstr, _Configuration.PKGCONN_CONFLICT ) ) )

						rctxt.last_fail_dot_graph = self.get_dot_graph_as_string()
						raise PkgConflictError(conflicts)
					else:
						for cv in conflicting_variants:
							variants.remove(cv)

						if (rctxt.verbosity == 2):
							print
							print "removed conflicting variants from " + pkg.short_name() + ':'
							for conflict in conflicts:
								print str(conflict)
		return num


	def resolve_common_variants(self, rctxt):
		"""
		for each package, find common package families within its variants, and add these to
		the configuration. For eg, if a pkg has 2 variants 'python-2.5' and 'python-2.6',
		then the inexact package 'python-2.5|2.6' will be added to the configuration
		(but only if ALL variants reference a 'python' package). Return the number of
		common package families resolved. Note that if a package contains a single variant,
		this this function will add every package in the variant to the configuration.
		"""

		num = 0
		config2 = self.copy()

		for name,pkg in self.pkgs.iteritems():

			variants = pkg.get_variants()
			if variants != None:

				# find common package families
				pkgname_sets = []
				pkgname_versions = {}
				pkgname_entries = {}

				for variant in variants:
					if (len(variant.working_list) > 0):
						pkgname_set = set()
						for pkgstr in variant.working_list:
							pkg_req = str_to_pkg_req(pkgstr, rctxt)
							pkgname_set.add(pkg_req.name)
							if not (pkg_req.name in pkgname_versions):
								pkgname_versions[pkg_req.name] = []
								pkgname_entries[pkg_req.name] = []
							pkgname_versions[pkg_req.name].append(pkg_req.version)
							pkgname_entries[pkg_req.name].append([ variant.working_list, pkgstr ])
						pkgname_sets.append(pkgname_set)

				if (len(pkgname_sets) > 0):
					common_pkgnames = pkgname_sets[0]
					for pkgname_set in pkgname_sets[1:]:
						common_pkgnames = common_pkgnames.intersection(pkgname_set)

					num += len(common_pkgnames)

					# add the union of each common package to the configuration,
					# and remove the packages from the variants' working lists
					for common_pkgname in common_pkgnames:
						ored_pkgs_str = common_pkgname + '-' +str('|').join(pkgname_versions[common_pkgname])
						pkg_req_ = str_to_pkg_req(ored_pkgs_str, rctxt.time_epoch)

						normalise_pkg_req(pkg_req_)
						config2.add_package(rctxt, pkg_req_, pkg)

						for entry in pkgname_entries[common_pkgname]:
							entry[0].remove(entry[1])

						if (rctxt.verbosity != 0):
							print
							print "removed common package family '" + common_pkgname + "' from " + pkg.short_name() + \
								"'s variants; config after adding " + pkg_req_.short_name() + ':'
						if (rctxt.verbosity == 1):
							print str(config2)
						elif (rctxt.verbosity == 2):
							config2.dump()

		self.swap(config2)
		return num

	def resolve_single_variant_packages(self, rctxt):
		"""
		find packages which have one non-conflicting, fully-resolved variant. These
		packages can now be fully resolved
		"""

		num = 0
		for name,pkg in self.pkgs.iteritems():
			if pkg.is_resolved():
				continue

			variants = pkg.get_variants()
			if (variants != None) and (len(variants) == 1):
				variant = variants[0]
				if (len(variant.working_list) == 0):

					# check resolved path exists
					root_path = pkg.base_path + '/' + str('/').join(variant.metadata)
					if not dir_exists(root_path):
						pkg_req_ = pkg.as_package_request()

						self.add_dot_graph_verbatim('"' + \
							pkg_req_.short_name() + ' NOT FOUND' + \
							'" [style=filled fillcolor="orangered"] ;')
						self.add_dot_graph_verbatim('"' + \
							pkg_req_.short_name() + '" -> "' + \
							pkg_req_.short_name() + ' NOT FOUND" ;')
						rctxt.last_fail_dot_graph = self.get_dot_graph_as_string()

						sys.stderr.write("Warning! Package not found: " + str(pkg_req_) + "\n")
						raise PkgNotFoundError(pkg_req_, root_path)

					pkg.resolve(root_path)
					num += 1

					if (rctxt.verbosity != 0):
						print
						print "resolved single-variant package " + pkg.short_name() + ':'
					if (rctxt.verbosity == 1):
						print str(self)
					elif (rctxt.verbosity == 2):
						print str(pkg)
		return num

	def dump(self):
		"""
		debug printout
		"""
		for name in self.families:
			pkg = self.pkgs[name]
			if (pkg.metadata == None):
				print pkg.short_name()
			else:
				print str(pkg)

	def __str__(self):
		"""
		short printout
		"""
		str_ = ""
		for name in self.families:
			pkg = self.pkgs[name]
			str_ += pkg.short_name()

			modif="("
			if pkg.is_resolved():
				modif += "r"
			elif pkg.is_metafile_resolved():
				modif += "b"
			else:
				modif += "u"
			if pkg.is_transitivity:
				modif += "t"
			str_ += modif + ") "

		return str_

	def short_str(self):
		"""
		even shorter printout
		"""
		str_ = ""
		for name in self.families:
			pkg = self.pkgs[name]
			str_ += pkg.short_name() + " "
		return str_



##############################################################################
# Internal Functions
##############################################################################

def get_system_package_paths():
	"""
	Get the system roots for package installations. REZ_PACKAGES_PATH is a colon-
	separated string, and the paths will be searched in order of appearance.
	"""
	syspathstr = os.getenv(REZ_PACKAGES_PATH_ENVVAR)
	if syspathstr:
		syspaths = syspathstr.split(':')
		return syspaths
	else:
		raise PkgSystemError(REZ_PACKAGES_PATH_ENVVAR + " is not set")


def pkg_to_pkg_req(pkg):
	"""
	Helper fn to convert a _Package to a PackageRequest
	"""
	return PackageRequest(pkg.name, str(pkg.version_range))


def normalise_pkg_req(pkg_req):
	"""
	Helper fn to turn a PackageRequest into a regular representation. It is possible
	to describe a package in a way that is not the same as it will end up in the
	system. This is perfectly fine, but it can result in confusing dot-graphs. For
	example, the package 'foo-1|1' is equivalent to 'foo-1'.
	"""
	version_range = VersionRange(pkg_req.version)
	pkg_req.version = str(version_range)


def process_commands(cmds):
	"""
	Given a list of commands which represent a configuration context,

	a) Find the first forms of X=$X:<something_else>, and drop the leading $X so
		that values aren't inherited from the existing environment;
	b) Find variable overwrites and raise an exception if found (ie, consecutive
		commands of form "X=something, X=something_else".

	This function returns the altered commands. Order of commands is retained.
	"""
	set_vars = {}
	new_cmds = []

	for cmd_ in cmds:

		if type(cmd_) == type([]):
			cmd = cmd_[0]
			pkgname = cmd_[1]
		else:
			cmd = cmd_
			pkgname = None

		if cmd.split()[0] == "export":

			# parse name, value
			var_val = cmd[len("export"):].split('=')
			if (len(var_val) != 2):
				raise PkgCommandError("invalid command:'" + cmd + "'")
			varname = var_val[0].split()[0]
			val = var_val[1]

			# has value already been set?
			val_is_set = (varname in set_vars)

			# check for variable self-reference (eg X=$X:foo etc)
			pos = val.find('$'+varname)
			if (pos == -1):
				if val_is_set:
					# no self-ref but previous val, this is a val overwrite
					raise PkgCommandError("the command set by '" + str(pkgname) + "':\n" + cmd + \
						"\noverwrites the variable set in a previous command by '" + str(set_vars[varname]) + "'")
			elif not val_is_set:
				# self-ref but no previous val, so strip self-ref out
				val = val.replace('$'+varname,'')

			# special case. CMAKE_MODULE_PATH is such a common case, but unusually uses ';' rather
			# than ':' to delineate, that I just allow ':' and do the switch here. Using ';' causes
			# probs because in bash it needs to be single-quoted, and users will forget to do that
			# in their package.yamls.
			if(varname == "CMAKE_MODULE_PATH"):
				val = val.strip(':;')
				val = val.replace(':', "';'")

			set_vars[varname] = pkgname
			new_cmds.append("export " + varname + '=' + val)

		else:
			new_cmds.append(cmd)

	return new_cmds


##############################################################################
# Statics
##############################################################################

syspaths = get_system_package_paths()

















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
