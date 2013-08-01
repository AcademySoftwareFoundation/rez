"""
rez-release

A tool for releasing rez - compatible projects centrally
"""

import sys
import os
import shutil
import inspect
import time
import subprocess
import rez_release_base as rrb
from rez_metafile import *
import versions

_release_classes = []

##############################################################################
# Exceptions
##############################################################################

class RezReleaseError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return str(self.value)

class RezReleaseUnsupportedMode(RezReleaseError):
	"""
	Raise this error during initialization of a RezReleaseMode sub-class to indicate
	that the mode is unsupported in the given context
	"""
	pass

##############################################################################
# Globals
##############################################################################

REZ_RELEASE_PATH_ENV_VAR = 		"REZ_RELEASE_PACKAGES_PATH"
EDITOR_ENV_VAR		 	= 		"REZ_RELEASE_EDITOR"
RELEASE_COMMIT_FILE 	= 		"rez-release-svn-commit.tmp"


##############################################################################
# Public Functions
##############################################################################

def register_release_mode(name, cls):
	"""
	Register a subclass of RezReleaseMode for performing a custom release procedure.
	"""
	assert inspect.isclass(cls) and issubclass(cls, RezReleaseMode), \
		"Provided class is not a subclass of RezReleaseMode"
	assert name not in list_release_modes(), \
		"Mode has already been registered"
	# put new entries at the front
	_release_classes.insert(0, (name, cls))

def list_release_modes():
	return [name for (name, cls) in _release_classes]

def list_available_release_modes(path):
	modes = []
	for name, cls in _release_classes:
		try:
			cls(path)
		except:
			pass
		else:
			modes.append(name)
	return modes

def release_from_path(path, commit_message, njobs, build_time, allow_not_latest,
					  mode='svn'):
	"""
	release a package from the given path on disk, copying to the relevant tag,
	and performing a fresh build before installing it centrally. If 'commit_message'
	is None, then the user will be prompted for input using the editor specified
	by $REZ_RELEASE_EDITOR.
	path: filepath containing the project to be released
	commit_message: None, or message string to write to svn, along with changelog
	njobs: number of threads to build with; passed to make via -j flag
	build_time: epoch time to build at. If 0, use current time
	allow_not_latest: if True, allows for releasing a tag that is not > the latest tag version
	"""
	cls = dict(_release_classes)[mode]
	rel = cls(path)
	rel.release(commit_message, njobs, build_time, allow_not_latest)

##############################################################################
# Implementation Classes
##############################################################################

class RezReleaseMode(object):
	'''
	Base class for all release modes
	'''
	def __init__(self, path):
		self.path = path
		
		# variables filled out in pre_build()
		self.metadata = None
		self.base_dir = None
		self.pkg_release_dir = None
		self.package_uuid_exists = None

	def release(self, commit_message, njobs, build_time, allow_not_latest):
		'''
		Main entry point for executing the release
		'''
		# TODO: implement commit message in a svn-agnostic way
		self.commit_message = commit_message
		self.njobs = njobs
		self.build_time = build_time
		self.allow_not_latest = allow_not_latest

		self.pre_build()
		self.build()
		self.install()
		self.post_install()

	def get_metadata(self):
		'''
		return a ConfigMetadata instance for this project's package.yaml file.
		'''
		# check for ./package.yaml
		if not os.access(self.path + "/package.yaml", os.F_OK):
			raise RezReleaseError(self.path + "/package.yaml not found")

		# load the package metadata
		metadata = ConfigMetadata(self.path + "/package.yaml")
		if (not metadata.version):
			raise RezReleaseError(self.path + "/package.yaml does not specify a version")
		try:
			self.this_version = versions.Version(metadata.version)
		except VersionError:
			raise RezReleaseError(self.path + "/package.yaml contains illegal version number")

		# metadata must have name
		if not metadata.name:
			raise RezReleaseError(self.path + "/package.yaml is missing name")

		# metadata must have uuid
		if not metadata.uuid:
			raise RezReleaseError(self.path + "/package.yaml is missing uuid")

		# .metadata must have description
		if not metadata.description:
			raise RezReleaseError(self.path + "/package.yaml is missing a description")

		# metadata must have authors
		if not metadata.authors:
			raise RezReleaseError(self.path + "/package.yaml is missing authors")

		return metadata

	def get_build_cmd(self, vararg):
		build_cmd = "rez-build" + \
			" -t " + str(self.build_time) + \
			" " + vararg + \
			" -- -- -j" + str(self.njobs)
		return build_cmd

	def get_install_cmd(self, vararg):
		build_cmd = "rez-build -n" + \
			" -t " + str(self.build_time) + \
			" " + vararg + \
			" -- -c -- install"
		return build_cmd

	def copy_source(self, build_dir):
		'''
		Copy the source to the build directory.

		This is particularly useful for revision control systems, which can
		export a clean unmodified copy
		'''
		def ignore(src, names):
			'''
			returns a list of names to ignore, given the current list
			'''
			if src == self.base_dir:
				return names
			return [x for x in names if x.startswith('.')]

		copytree(os.getcwd(), build_dir, symlinks=True,
				ignore=ignore)

	def pre_build(self):
		'''
		Fill out variables and check for problems
		'''
		self.metadata = self.get_metadata()

		self.pkg_release_dir = os.getenv(REZ_RELEASE_PATH_ENV_VAR)
		if not self.pkg_release_dir:
			raise RezReleaseError("$" + REZ_RELEASE_PATH_ENV_VAR + " is not set.")

		# check uuid against central uuid for this package family, to ensure that
		# we are not releasing over the top of a totally different package due to naming clash
		self.pkg_release_dir = os.path.join(self.pkg_release_dir, self.metadata.name)
		self.package_uuid_file = os.path.join(self.pkg_release_dir,  "package.uuid")

		try:
			existing_uuid = open(self.package_uuid_file).read().strip()
		except Exception:
			self.package_uuid_exists = False
			existing_uuid = self.metadata.uuid
		else:
			self.package_uuid_exists = True

		if(existing_uuid != self.metadata.uuid):
			raise RezReleaseError("the uuid in '" + self.package_uuid_file + \
				"' does not match this package's uuid - you may have a package name clash. All package " + \
				"names must be unique.")

		self.variants = self.metadata.get_variants()
		if not self.variants:
			self.variants = [ None ]

		# create base dir to do clean builds from
		self.base_dir = os.path.join(os.getcwd(), "build", "rez-release")
		if os.path.exists(self.base_dir):
			if os.path.islink(self.base_dir):
				os.remove(self.base_dir)
			elif os.path.isdir(self.base_dir):
				shutil.rmtree(self.base_dir)
			else:
				os.remove(self.base_dir)

		os.makedirs(self.base_dir)

		# take note of the current time, and use it as the build time for all variants. This ensures
		# that all variants will find the same packages, in case some new packages are released
		# during the build.
		if str(self.build_time) == "0":
			self.build_time = subprocess.Popen("date +%s", stdout=subprocess.PIPE, shell=True).communicate()[0]
			self.build_time = self.build_time.strip()

	def build(self):
		'''
		Perform build of all variants
		'''
		# svn-export each variant out to a clean directory, and build it locally. If any
		# builds fail then this release is aborted

		print
		print("---------------------------------------------------------")
		print("rez-release: building...")
		print("---------------------------------------------------------")

		for varnum, variant in enumerate(self.variants):
			self.build_variant(variant, varnum)

	def build_variant(self, variant, varnum):
		'''
		Build a single variant
		'''
		if variant:
			varname = "project variant #" + str(varnum)
			vararg = "-v " + str(varnum)
			subdir = os.path.join(self.base_dir, str(varnum))
		else:
			varnum = ''
			varname = "project"
			vararg = ''
			subdir = self.base_dir
		print
		print("rez-release: creating clean copy of " + varname + " to " + subdir + "...")

		if os.path.exists(subdir):
			shutil.rmtree(subdir)

		self.copy_source(subdir)

		# build it
		build_cmd = self.get_build_cmd(vararg)

		print
		print("rez-release: building " + varname + " in " + subdir + "...")
		print("rez-release: invoking: " + build_cmd)

		build_cmd = "cd " + subdir + " ; " + build_cmd
		pret = subprocess.Popen(build_cmd, shell=True)
		pret.communicate()
		if (pret.returncode != 0):
			raise RezReleaseError("rez-release: build failed")

	def install(self):
		'''
		Perform installation of all variants
		'''
		# now install the variants
		print
		print("---------------------------------------------------------")
		print("rez-release: installing...")
		print("---------------------------------------------------------")

		# create the package.uuid file, if it doesn't exist
		if not self.package_uuid_exists:
			os.makedirs(self.pkg_release_dir)

			f = open(self.package_uuid_file, 'w')
			f.write(self.metadata.uuid)
			f.close()

		# install the variants
		for varnum, variant in enumerate(self.variants):
			self.install_variant(variant, varnum)

	def install_variant(self, variant, varnum):
		'''
		Install a single variant
		'''
		if variant:
			varname = "project variant #" + str(varnum)
			vararg = "-v " + str(varnum)
		else:
			varnum = ''
			varname = 'project'
			vararg = ''
		subdir = self.base_dir + '/' + str(varnum) + '/'

		# determine install self.path
		pret = subprocess.Popen("cd " + subdir + " ; rez-build -i " + vararg, \
			stdout=subprocess.PIPE, shell=True)
		instpath, instpath_err = pret.communicate()
		if (pret.returncode != 0):
			raise RezReleaseError("rez-release: install failed!! A partial central installation may " + \
				"have resulted, please see to this immediately - it should probably be removed.")
		instpath = instpath.strip()

		print
		print("rez-release: installing " + varname + " from " + subdir + " to " + instpath + "...")

		# run rez-build, and:
		# * manually specify the svn-url to write into self.metadata;
		# * manually specify the changelog file to use
		# these steps are needed because the code we're building has been svn-exported, thus
		# we don't have any svn context.

		build_cmd = self.get_install_cmd(vararg)
		pret = subprocess.Popen("cd " + subdir + " ; " + build_cmd, shell=True)

		pret.wait()
		if (pret.returncode != 0):
			raise RezReleaseError("rez-release: install failed!! A partial central installation may " + \
				"have resulted, please see to this immediately - it should probably be removed.")

		# Prior to locking down the installation, remove any .pyc files that may have been spawned
		pret = subprocess.Popen("cd " + instpath + " ; rm -f `find -type f | grep '\.pyc$'`", shell=True)
		pret.wait()

		# Remove write permissions from all installed files.
		pret = subprocess.Popen("cd " + instpath + " ; chmod a-w `find -type f | grep -v '\.self.metadata'`", shell=True)
		pret.wait()

		# Remove write permissions on dirs that contain py files
		pret = subprocess.Popen("cd " + instpath + " ; find -name '*.py'", shell=True, stdout=subprocess.PIPE)
		cmdout, cmderr = pret.communicate()
		if len(cmdout.strip()) > 0:
			pret = subprocess.Popen("cd " + instpath + " ; chmod a-w `find -name '*.py' | xargs -n 1 dirname | sort | uniq`", shell=True)
			pret.wait()

	def post_install(self):
		'''
		Final stage after installation
		'''
		# the very last thing we do is write out the current date-time to a metafile. This is
		# used by rez to specify when a package 'officially' comes into existence.
		time_metafile = os.path.join(self.pkg_release_dir, self.metadata.version,
									'.metadata' , 'release_time.txt')
		timef = open(time_metafile, 'w')
		time_epoch = int(time.mktime(time.localtime()))
		timef.write(str(time_epoch) + '\n')
		timef.close()

		# email
		usr = os.getenv("USER", "unknown.user")
		pkgname = "%s-%s" % (self.metadata.name, str(self.this_version))
		subject = "[rez] [release] %s released %s" % (usr, pkgname)
		if len(self.variants) > 1:
			subject += " (%d variants)" % len(self.variants)
		rrb.send_release_email(subject, self.commit_message)

		print
		print("rez-release: your package was released successfully.")
		print

register_release_mode('base', RezReleaseMode)

##############################################################################
# Utilities
##############################################################################

def copytree(src, dst, symlinks=False, ignore=None):
	'''
	copytree that supports hard-linking
	'''
	print "copying directory", src
	names = os.listdir(src)
	if ignore is not None:
		ignored_names = ignore(src, names)
	else:
		ignored_names = set()

	os.makedirs(dst)
	errors = []
	for name in names:
		if name in ignored_names:
			continue
		srcname = os.path.join(src, name)
		dstname = os.path.join(dst, name)
		try:
			if symlinks and os.path.islink(srcname):
				linkto = os.readlink(srcname)
				os.symlink(linkto, dstname)
			elif os.path.isdir(srcname):
				copytree(srcname, dstname, symlinks, ignore)
			else:
				#shutil.copy2(srcname, dstname)
				os.link(srcname, dstname)
		# XXX What about devices, sockets etc.?
		except (IOError, os.error) as why:
			errors.append((srcname, dstname, str(why)))
		# catch the Error from the recursive copytree so that we can
		# continue with other files
		except shutil.Error as err:
			errors.extend(err.args[0])
	try:
		shutil.copystat(src, dst)
	except shutil.WindowsError:
		# can't copy file access times on Windows
		pass
	except OSError as why:
		errors.extend((src, dst, str(why)))
	if errors:
		raise shutil.Error(errors)

class SvnValueCallback:
	"""
	simple functor class
	"""
	def __init__(self, value):
		self.value = value
	def __call__(self):
		return True, self.value

def svn_get_client(path):
	import pysvn
	# check we're in an svn working copy
	client = pysvn.Client()
	client.set_interactive(True)
	client.set_auth_cache(False)
	client.set_store_passwords(False)
	client.callback_get_login = getSvnLogin
	svn_entry = client.info(path)
	if not svn_entry:
		raise RezReleaseError("'" + path + "' is not an svn working copy")
	return client, str(svn_entry["url"])

def svn_url_exists(client, url):
	"""
	return True if the svn url exists
	"""
	import pysvn
	try:
		svnlist = client.info2(url, recurse = False)
		return len( svnlist ) > 0
	except pysvn.ClientError:
		return False


def get_last_changed_revision(client, url):
	"""
	util func, get last revision of url
	"""
	import pysvn
	try:
		svn_entries = client.info2(url, pysvn.Revision(pysvn.opt_revision_kind.head), recurse=False)
		if len(svn_entries) == 0:
			raise RezReleaseError("svn.info2() returned no results on url '" + url + "'")
		return svn_entries[0][1].last_changed_rev
	except pysvn.ClientError, ce:
		raise RezReleaseError("svn.info2() raised ClientError: %s"%ce)


def getSvnLogin(realm, username, may_save):
	"""
	provide svn with permissions. @TODO this will have to be updated to take
	into account automated releases etc.
	"""
	import getpass

	print "svn requires a password for the user '" + username + "':"
	pwd = ''
	while(pwd.strip() == ''):
		pwd = getpass.getpass("--> ")

	return True, username, pwd, False

class SvnRezRelease(RezReleaseMode):
	def __init__(self, path):
		super(SvnRezRelease, self).__init__(path)
		
		self.svnc, self.this_url = svn_get_client(self.path)

		# variables filled out in pre_build()
		self.tag_url = None
		self.changelogFile = None
		self.self.changeLog = None
		self.editor = None

	def get_metadata(self):
		result = super(SvnRezRelease, self).get_metadata()
		# check that ./package.yaml is under svn control
		if not svn_url_exists(self.svnc, self.this_url + "/package.yaml"):
			raise RezReleaseError(self.path + "/package.yaml is not under source control")
		return result

	def get_build_cmd(self, vararg):
		build_cmd = "rez-build" + \
			" -t " + str(self.build_time) + \
			" " + vararg + \
			" -s " + self.tag_url + \
			" -c " + self.changelogFile + \
			" -- -- -j" + str(self.njobs)
		return build_cmd

	def get_install_cmd(self, vararg):
		build_cmd = "rez-build -n" + \
			" -t " + str(self.build_time) + \
			" " + vararg + \
			" -s " + self.tag_url + \
			" -c " + self.changelogFile + \
			" -- -c -- install"
		return build_cmd

	def copy_source(self, build_dir):
		# svn-export it. pysvn is giving me some false assertion crap on 'is_canonical(self.path)' here, hence shell
		pret = subprocess.Popen(["svn", "export", self.this_url, build_dir])
		pret.communicate()
		if (pret.returncode != 0):
			raise RezReleaseError("rez-release: svn export failed")

	def pre_build(self):
		super(SvnRezRelease, self).pre_build()
		
		if (self.commit_message == None):
			# get preferred self.editor for commit message
			self.editor = os.getenv(EDITOR_ENV_VAR)
			if not self.editor:
				raise RezReleaseError("rez-release: $" + EDITOR_ENV_VAR + " is not set.")

		# find the base self.path, ie where 'trunk', 'branches', 'tags' should be
		pos_tr = self.this_url.find("/trunk")
		pos_br = self.this_url.find("/branches")
		pos = max(pos_tr, pos_br)
		if (pos == -1):
			raise RezReleaseError(self.path + "is not in a branch or trunk")
		base_url = self.this_url[:pos]

		# check we're in a state to release (no modified/out-of-date files etc)
		status_list = self.svnc.status(self.path, get_all=False, update=True)
		status_list_known = []
		for status in status_list:
			if status.entry:
				status_list_known.append(status)
		if len(status_list_known) > 0:
			raise RezReleaseError("'" + self.path + "' is not in a state to release - you may need to " + \
				"svn-checkin and/or svn-update: " + str(status_list_known))

		# do an update
		print("rez-release: svn-updating...")
		self.svnc.update(self.path)

		tags_url = base_url + "/tags"
		self.tag_url = tags_url + '/' + str(self.this_version)

		# check that this tag does not already exist
		if svn_url_exists(self.svnc, self.tag_url):
			raise RezReleaseError("cannot release: the tag '" + self.tag_url + "' already exists in svn." + \
				" You may need to up your version, svn-checkin and try again.")

		# find latest tag, if it exists. Get the changelog at the same time.
		pret = subprocess.Popen("rez-svn-changelog", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		self.changeLog, changeLog_err = pret.communicate()

		if (pret.returncode == 0) and (not self.allow_not_latest):
			last_tag_str = self.changeLog.splitlines()[0].split()[-1].replace('/',' ').replace(':',' ').split()[-1]
			if (last_tag_str != "(NONE)") and (last_tag_str[0] != 'v'):
				# make sure our version is newer than the last tagged release
				last_tag_version = versions.Version(last_tag_str)
				if self.this_version <= last_tag_version:
					raise RezReleaseError("cannot release: current version '" + self.metadata.version + \
						"' is not greater than the latest tag '" + last_tag_str + \
						"'. You may need to up your version, svn-checkin and try again.")

		# write the changelog to file, so that rez-build can install it as metadata
		self.changelogFile = os.getcwd() + '/build/rez-release-changelog.txt'
		chlogf = open(self.changelogFile, 'w')
		chlogf.write(self.changeLog)
		chlogf.close()

	def build_variant(self, variant, varnum):
		super(SvnRezRelease, self).build_variant(variant, varnum)

	def install(self):
		super(SvnRezRelease, self).install()

		if (self.commit_message is not None):
			self.commit_message += '\n' + self.changeLog
		else:
			# prompt for tag comment, automatically setting to the change-log
			self.commit_message = "\n\n" + self.changeLog

			tmpf = self.base_dir + '/' + RELEASE_COMMIT_FILE
			f = open(tmpf, 'w')
			f.write(self.commit_message)
			f.close()

			pret = subprocess.Popen(self.editor + " " + tmpf, shell=True)
			pret.wait()
			if (pret.returncode == 0):
				# if commit file was unchanged, then give a chance to abort the release
				new_commit_message = open(tmpf).read()
				if (new_commit_message == self.commit_message):
					pret = subprocess.Popen( \
						'read -p "Commit message unchanged - (a)bort or (c)ontinue? "' + \
						' ; if [ "$REPLY" != "c" ]; then exit 1 ; fi', shell=True)
					pret.wait()
					if (pret.returncode != 0):
						print("release aborted by user")
						pret = subprocess.Popen("rm -f " + tmpf, shell=True)
						pret.wait()
						sys.exit(1)

				self.commit_message = new_commit_message

			pret = subprocess.Popen("rm -f " + tmpf, shell=True)
			pret.wait()

	def install_variant(self, variant, varnum):
		super(SvnRezRelease, self).install_variant(variant, varnum)

	def post_install(self):

		print
		print("---------------------------------------------------------")
		print("rez-release: tagging...")
		print("---------------------------------------------------------")
		print

		# at this point all variants have built and installed successfully. Copy to the new tag
		print("rez-release: creating project tag in: " + self.tag_url + "...")
		self.svnc.callback_get_log_message = SvnValueCallback(self.commit_message)

		self.svnc.copy2([ (self.this_url,) ], \
			self.tag_url, make_parents=True )

		super(SvnRezRelease, self).post_install()

register_release_mode('svn', SvnRezRelease)





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
