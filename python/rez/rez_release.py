"""
rez-release

A tool for releasing rez - compatible projects centrally
"""

import sys
import os
import time
import pysvn
import subprocess
from rez_metafile import *
import versions


##############################################################################
# Exceptions
##############################################################################

class RezReleaseError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return str(self.value)


##############################################################################
# Globals
##############################################################################

REZ_RELEASE_PATH_ENV_VAR = 		"REZ_RELEASE_PACKAGES_PATH"
EDITOR_ENV_VAR		 	= 		"REZ_RELEASE_EDITOR"
RELEASE_COMMIT_FILE 	= 		"rez-release-svn-commit.tmp"


##############################################################################
# Public Functions
##############################################################################


def release_from_path(path, commit_message, njobs, build_time, allow_not_latest):
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
	# check for ./package.yaml
	if not os.access(path + "/package.yaml", os.F_OK):
		raise RezReleaseError(path + "/package.yaml not found")

	# check we're in an svn working copy
	svnc = pysvn.Client()
	svnc.set_interactive( True )
	svnc.set_auth_cache( False )
	svnc.set_store_passwords( False )
	svnc.callback_get_login = getSvnLogin

	svn_entry = svnc.info(path)
	if not svn_entry:
		raise RezReleaseError("'" + path + "' is not an svn working copy")
	this_url = str(svn_entry["url"])

	# check that ./package.yaml is under svn control
	if not svn_url_exists(svnc, this_url + "/package.yaml"):
		raise RezReleaseError(path + "/package.yaml is not under source control")

	if (commit_message == None):
		# get preferred editor for commit message
		editor = os.getenv(EDITOR_ENV_VAR)
		if not editor:
			raise RezReleaseError("rez-release: $" + EDITOR_ENV_VAR + " is not set.")

	# load the package metadata
	metadata = ConfigMetadata(path + "/package.yaml")
	if (not metadata.version):
		raise RezReleaseError(path + "/package.yaml does not specify a version")
	try:
		this_version = versions.Version(metadata.version)
	except VersionError:
		raise RezReleaseError(path + "/package.yaml contains illegal version number")

	# metadata must have name
	if not metadata.name:
		raise RezReleaseError(path + "/package.yaml is missing name")

	# metadata must have uuid
	if not metadata.uuid:
		raise RezReleaseError(path + "/package.yaml is missing uuid")

	# metadata must have description
	if not metadata.description:
		raise RezReleaseError(path + "/package.yaml is missing a description")

	# metadata must have authors
	if not metadata.authors:
		raise RezReleaseError(path + "/package.yaml is missing authors")

	pkg_release_path = os.getenv(REZ_RELEASE_PATH_ENV_VAR)
	if not pkg_release_path:
		raise RezReleaseError("$" + REZ_RELEASE_PATH_ENV_VAR + " is not set.")

	# check uuid against central uuid for this package family, to ensure that
	# we are not releasing over the top of a totally different package due to naming clash
	existing_uuid = None
	package_uuid_dir = pkg_release_path + '/' + metadata.name
	package_uuid_file = package_uuid_dir + "/package.uuid"
	package_uuid_exists = True

	try:
		existing_uuid = open(package_uuid_file).read().strip()
	except Exception:
		package_uuid_exists = False
		existing_uuid = metadata.uuid

	if(existing_uuid != metadata.uuid):
		raise RezReleaseError("the uuid in '" + package_uuid_file + \
			"' does not match this package's uuid - you may have a package name clash. All package " + \
			"names must be unique.")

	# find the base path, ie where 'trunk', 'branches', 'tags' should be
	pos_tr = this_url.find("/trunk")
	pos_br = this_url.find("/branches")
	pos = max(pos_tr, pos_br)
	if (pos == -1):
		raise RezReleaseError(path + "is not in a branch or trunk")
	base_url = this_url[:pos]

	# check we're in a state to release (no modified/out-of-date files etc)
	status_list = svnc.status(path, get_all=False, update=True)
	status_list_known = []
	for status in status_list:
		if status.entry:
			status_list_known.append(status)
	if len(status_list_known) > 0:
		raise RezReleaseError("'" + path + "' is not in a state to release - you may need to " + \
			"svn-checkin and/or svn-update: " + str(status_list_known))

	# do an update
	print("rez-release: svn-updating...")
	svnc.update(path)

	tags_url = base_url + "/tags"
	latest_tag = []
	latest_tag_str = ''
	changeLog = ''

	tag_url = tags_url + '/' + str(this_version)

	# check that this tag does not already exist
	if svn_url_exists(svnc, tag_url):
		raise RezReleaseError("cannot release: the tag '" + tag_url + "' already exists in svn." + \
			" You may need to up your version, svn-checkin and try again.")

	# find latest tag, if it exists. Get the changelog at the same time.
	pret = subprocess.Popen("rez-svn-changelog", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	changeLog, changeLog_err = pret.communicate()

	if (pret.returncode == 0) and (not allow_not_latest):
		last_tag_str = changeLog.splitlines()[0].split()[-1].replace('/',' ').replace(':',' ').split()[-1]
		if (last_tag_str != "(NONE)") and (last_tag_str[0] != 'v'):
			# make sure our version is newer than the last tagged release
			last_tag_version = versions.Version(last_tag_str)
			if this_version <= last_tag_version:
				raise RezReleaseError("cannot release: current version '" + metadata.version + \
					"' is not greater than the latest tag '" + last_tag_str + \
					"'. You may need to up your version, svn-checkin and try again.")

	# create base dir to do clean builds from
	base_dir = os.getcwd() + "/build/rez-release"
	pret = subprocess.Popen("rm -rf " + base_dir, shell=True)
	pret.communicate()
	pret = subprocess.Popen("mkdir -p " + base_dir, shell=True)
	pret.communicate()

	# write the changelog to file, so that rez-build can install it as metadata
	changelogFile = os.getcwd() + '/build/rez-release-changelog.txt'
	chlogf = open(changelogFile, 'w')
	chlogf.write(changeLog)
	chlogf.close()

	# svn-export each variant out to a clean directory, and build it locally. If any
	# builds fail then this release is aborted
	varnum = -1
	variants = metadata.get_variants()
	variants_ = variants
	varname = "project"

	if not variants:
		variants_ = [ None ]
		varnum = ''
		vararg = ''

	print
	print("---------------------------------------------------------")
	print("rez-release: building...")
	print("---------------------------------------------------------")

	# take note of the current time, and use it as the build time for all variants. This ensures
	# that all variants will find the same packages, in case some new packages are released
	# during the build.
	if str(build_time) == "0":
		build_time = subprocess.Popen("date +%s", stdout=subprocess.PIPE, shell=True).communicate()[0]
		build_time = build_time.strip()

	timearg = "-t " + str(build_time)

	for variant in variants_:
		if variant:
			varnum += 1
			varname = "project variant #" + str(varnum)
			vararg = "-v " + str(varnum)

		subdir = base_dir + '/' + str(varnum) + '/'
		print
		print("rez-release: svn-exporting clean copy of " + varname + " to " + subdir + "...")

		# remove subdir in case it already exists
		pret = subprocess.Popen("rm -rf " + subdir, shell=True)
		pret.communicate()
		if (pret.returncode != 0):
			raise RezReleaseError("rez-release: deletion of '" + subdir + "' failed")

		# svn-export it. pysvn is giving me some false assertion crap on 'is_canonical(path)' here, hence shell
		pret = subprocess.Popen(["svn","export",this_url,subdir])
		pret.communicate()
		if (pret.returncode != 0):
			raise RezReleaseError("rez-release: svn export failed")

		# build it
		build_cmd = "rez-build" + \
			" " + timearg + \
			" " + vararg + \
			" -s " + tag_url + \
			" -c " + changelogFile + \
			" -- -- -j" + str(njobs)

		print
		print("rez-release: building " + varname + " in " + subdir + "...")
		print("rez-release: invoking: " + build_cmd)

		build_cmd = "cd " + subdir + " ; " + build_cmd
		pret = subprocess.Popen(build_cmd, shell=True)
		pret.communicate()
		if (pret.returncode != 0):
			raise RezReleaseError("rez-release: build failed")

	# now install the variants
	varnum = -1

	if not variants:
		variants_ = [ None ]
		varnum = ''
		vararg = ''

	print
	print("---------------------------------------------------------")
	print("rez-release: installing...")
	print("---------------------------------------------------------")

	# create the package.uuid file, if it doesn't exist
	if not package_uuid_exists:
		pret = subprocess.Popen("mkdir -p " + package_uuid_dir, shell=True)
		pret.wait()

		pret = subprocess.Popen("echo " + metadata.uuid + " > " + package_uuid_file, \
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
		pret.communicate()

	# install the variants
	for variant in variants_:
		if variant:
			varnum += 1
			varname = "project variant #" + str(varnum)
			vararg = "-v " + str(varnum)

		subdir = base_dir + '/' + str(varnum) + '/'

		# determine install path
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
		# * manually specify the svn-url to write into metadata;
		# * manually specify the changelog file to use
		# these steps are needed because the code we're building has been svn-exported, thus
		# we don't have any svn context.
		pret = subprocess.Popen("cd " + subdir + " ; rez-build -n" + \
			" " + timearg + \
			" " + vararg + \
			" -s " + tag_url + \
			" -c " + changelogFile + \
			" -- -c -- install", shell=True)

		pret.wait()
		if (pret.returncode != 0):
			raise RezReleaseError("rez-release: install failed!! A partial central installation may " + \
				"have resulted, please see to this immediately - it should probably be removed.")

		# Prior to locking down the installation, remove any .pyc files that may have been spawned
		pret = subprocess.Popen("cd " + instpath + " ; rm -f `find -type f | grep '\.pyc$'`", shell=True)
		pret.wait()

		# Remove write permissions from all installed files.
		pret = subprocess.Popen("cd " + instpath + " ; chmod a-w `find -type f | grep -v '\.metadata'`", shell=True)
		pret.wait()

		# Remove write permissions on dirs that contain py files
		pret = subprocess.Popen("cd " + instpath + " ; find -name '*.py'", shell=True, stdout=subprocess.PIPE)
		cmdout, cmderr = pret.communicate()
		if len(cmdout.strip()) > 0:
			pret = subprocess.Popen("cd " + instpath + " ; chmod a-w `find -name '*.py' | xargs -n 1 dirname | sort | uniq`", shell=True)
			pret.wait()

	if (commit_message != None):
		commit_message += '\n' + changeLog
	else:
		# prompt for tag comment, automatically setting to the change-log
		commit_message = "\n\n" + changeLog

		tmpf = base_dir + '/' + RELEASE_COMMIT_FILE
		f = open(tmpf, 'w')
		f.write(commit_message)
		f.close()

		pret = subprocess.Popen(editor + " " + tmpf, shell=True)
		pret.wait()
		if (pret.returncode == 0):
			# if commit file was unchanged, then give a chance to abort the release
			new_commit_message = open(tmpf).read()
			if (new_commit_message == commit_message):
				pret = subprocess.Popen( \
					'read -p "Commit message unchanged - (a)bort or (c)ontinue? "' + \
					' ; if [ "$REPLY" != "c" ]; then exit 1 ; fi', shell=True)
				pret.wait()
				if (pret.returncode != 0):
					print("release aborted by user")
					pret = subprocess.Popen("rm -f " + tmpf, shell=True)
					pret.wait()
					sys.exit(1)

			commit_message = new_commit_message

		pret = subprocess.Popen("rm -f " + tmpf, shell=True)
		pret.wait()

	print
	print("---------------------------------------------------------")
	print("rez-release: tagging...")
	print("---------------------------------------------------------")
	print

	# at this point all variants have built and installed successfully. Copy to the new tag
	print("rez-release: creating project tag in: " + tag_url + "...")
	svnc.callback_get_log_message = SvnValueCallback(commit_message)

	svnc.copy2([ (this_url,) ], \
		tag_url, make_parents=True )

	# the very last thing we do is write out the current date-time to a metafile. This is
	# used by rez to specify when a package 'officially' comes into existence.
	this_pkg_release_path = pkg_release_path + '/' + metadata.name + '/' + metadata.version
	time_metafile = this_pkg_release_path + '/.metadata/release_time.txt'
	timef = open(time_metafile, 'w')
	time_epoch = int(time.mktime(time.localtime()))
	timef.write(str(time_epoch) + '\n')
	timef.close()

	print
	print("rez-release: your package was released successfully.")
	print




##############################################################################
# Utilities
##############################################################################

class SvnValueCallback:
	"""
	simple functor class
	"""
	def __init__(self, value):
		self.value = value
	def __call__(self):
		return True, self.value


def svn_url_exists(client, url):
	"""
	return True if the svn url exists
	"""
	try:
		svnlist = client.info2(url, recurse = False)
		return len( svnlist ) > 0
	except pysvn.ClientError:
		return False


def get_last_changed_revision(client, url):
	"""
	util func, get last revision of url
	"""
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
