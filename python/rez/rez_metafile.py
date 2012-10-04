"""
Class for loading and verifying rez metafiles
"""

import yaml
import subprocess
import os


class ConfigMetadataError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return str(self.value)


# TODO this class is too heavy
class ConfigMetadata:
	"""
	metafile. An incorrectly-formatted file will result in either a yaml exception (if
	the syntax is wrong) or a ConfigMetadataError (if the content is wrong). An empty
	metafile is acceptable, and is supported for fast integration of 3rd-party packages
	"""

	# file format versioning, only update this if the package.yamls have to change
	# format in a way that is not backwards compatible
	METAFILE_VERSION = 0

	def __init__(self, filename):
		self.filename = filename
		self.config_version = ConfigMetadata.METAFILE_VERSION
		self.uuid = None
		self.authors = None
		self.description = None
		self.name = None
		self.version = None
		self.help = None
		self.requires = None
		self.build_requires = None
		self.variants = None
		self.commands = None

		with open(filename) as f:
			self.metadict = yaml.load(f.read()) or {}

		if self.metadict:
			###############################
			# Common content
			###############################

			if (type(self.metadict) != dict):
				raise ConfigMetadataError("package metafile '" + self.filename + \
					"' contains non-dictionary root node")

			# config_version
			if not ("config_version" in self.metadict):
				raise ConfigMetadataError("package metafile '" + self.filename + \
					"' is missing 'config_version'")
			else:
				sysver = self.metadict["config_version"]
				try:
					self.config_version = int(sysver)
				except (ValueError, TypeError):
					raise ConfigMetadataError("package metafile '" + self.filename + \
						"' contains invalid config version '" + str(sysver) + "'")

				if (self.config_version < 0) or (self.config_version > ConfigMetadata.METAFILE_VERSION):
					raise ConfigMetadataError("package metafile '" + self.filename + \
						"' contains invalid config version '" + str(self.config_version) + "'")

			def _get_str(label):
				val = self.metadict.get(label)
				if val is not None:
					return str(val).strip()
				return None

			self.uuid			= _get_str("uuid")
			self.description 	= _get_str("description")
			self.version 		= _get_str("version")
			self.name 			= _get_str("name")
			self.help 			= _get_str("help")

			# authors
			if "authors" in self.metadict:
				self.authors = self.metadict["authors"]
				if (type(self.authors) != list):
					raise ConfigMetadataError("package metafile '" + self.filename + \
						"' contains 'authors' entry which is not a list")

			# config-version-specific content
			if (self.config_version == 0):
				self.load_0();

	def delete_nonessentials(self):
		"""
		Delete everything not needed for package resolving.
		"""
		if self.uuid:
			del self.metadict["uuid"]
			self.uuid = None
		if self.description:
			del self.metadict["description"]
			self.description = None
		if self.help:
			del self.metadict["help"]
			self.help = None
		if self.authors:
			del self.metadict["authors"]
			self.authors = None

	def get_requires(self, include_build_reqs = False):
		"""
		Returns the required package names, if any
		"""
		if include_build_reqs:
			reqs = []
			# add build-reqs beforehand since they will tend to be more specifically-
			# versioned, this will speed up resolution times
			if self.build_requires:
				reqs += self.build_requires
			if self.requires:
				reqs += self.requires

			if len(reqs) > 0:
				return reqs
			else:
				return None
		else:
			return self.requires

	def get_build_requires(self):
		"""
		Returns the build-required package names, if any
		"""
		return self.build_requires

	def get_variants(self):
		"""
		Returns the variants, if any
		"""
		return self.variants

	def get_commands(self):
		"""
		Returns the commands, if any
		"""
		return self.commands

	def get_string_replace_commands(self, version, base, root):
		"""
		Get commands with string replacement
		"""
		if self.commands:

			vernums = version.split('.') + [ '', '' ]
			major_version = vernums[0]
			minor_version = vernums[1]
			user = os.getenv("USER", "UNKNOWN_USER")

			new_cmds = []
			for cmd in self.commands:
				cmd = cmd.replace("!VERSION!", version)
				cmd = cmd.replace("!MAJOR_VERSION!", major_version)
				cmd = cmd.replace("!MINOR_VERSION!", minor_version)
				cmd = cmd.replace("!BASE!", base)
				cmd = cmd.replace("!ROOT!", root)
				cmd = cmd.replace("!USER!", user)
				new_cmds.append(cmd)
			return new_cmds
		return None

	def load_0(self):
		"""
		Load config_version=0
		"""
		# requires
		if "requires" in self.metadict:
			self.requires = self.metadict["requires"]
			if (type(self.requires) != list):
				raise ConfigMetadataError("package metafile '" + self.filename + \
					"' contains non-list 'requires' node")
			if (len(self.requires) == 0):
				self.requires = None
			else:
				req0 = self.requires[0]
				if (type(req0) != str):
					raise ConfigMetadataError("package metafile '" + self.filename + \
						"' contains non-string 'requires' entries")

		# build_requires
		if "build_requires" in self.metadict:
			self.build_requires = self.metadict["build_requires"]
			if (type(self.build_requires) != list):
				raise ConfigMetadataError("package metafile '" + self.filename + \
					"' contains non-list 'build_requires' node")
			if (len(self.build_requires) == 0):
				self.build_requires = None
			else:
				req0 = self.build_requires[0]
				if (type(req0) != str):
					raise ConfigMetadataError("package metafile '" + self.filename + \
						"' contains non-string 'build_requires' entries")

		# variants
		if "variants" in self.metadict:
			self.variants = self.metadict["variants"]
			if (type(self.variants) != list):
				raise ConfigMetadataError("package metafile '" + self.filename + \
					"' contains non-list 'variants' node")
			if (len(self.variants) == 0):
				self.variants = None
			else:
				var0 = self.variants[0]
				if (type(var0) != list):
					raise ConfigMetadataError("package metafile '" + self.filename + \
						"' contains non-list 'variants' entries")

		# commands
		if "commands" in self.metadict:
			self.commands = self.metadict["commands"]
			if (type(self.commands) != list):
				raise ConfigMetadataError("package metafile '" + self.filename + \
					"' contains non-list 'commands' node")
			if (len(self.commands) == 0):
				self.commands = None



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
