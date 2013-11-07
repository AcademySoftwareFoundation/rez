"""
Class for loading and verifying rez metafiles
"""

import yaml
import os
import textwrap
import re
from collections import defaultdict
from rez_util import to_posixpath

_configs = defaultdict(list)

#------------------------------------------------------------------------------
# Exceptions
#------------------------------------------------------------------------------

class MetadataError(Exception):
    pass

class MetadataKeyError(MetadataError, KeyError):
    def __init__(self, filename, entry_id):
        self.filename = filename
        self.entry_id = entry_id

    def __str__(self):
        return "%s: missing required entry %s" % (self.filename, self.entry_id)

class MetadataTypeError(MetadataError, TypeError):
    def __init__(self, filename, entry_id, expected_type, actual_type):
        self.filename = filename
        self.entry_id = entry_id
        self.expected_type = expected_type
        self.actual_type = actual_type

    def __str__(self):
        return ("'%s': entry %s has incorrect data type: "
                "expected %s. got %s" % (self.filename, self.entry_id,
                                         self.expected_type.__name__,
                                         self.actual_type.__name__))

class MetadataValueError(MetadataError, ValueError):
    def __init__(self, filename, entry_id, value):
        self.filename = filename
        self.entry_id = entry_id
        self.value = value

    def __str__(self):
        return ("'%s': entry %s has invalid value: %r" % (self.filename,
                                                          self.entry_id,
                                                          self.value))

#------------------------------------------------------------------------------
# Utilities
#------------------------------------------------------------------------------

class AttrDict(dict):
    """
    A dictionary with attribute-based lookup
    """
    def __getattr__(self, attr):
        if attr.startswith('__') and attr.endswith('__'):
            d = self.__dict__
        else:
            d = self
        try:
            return d[attr]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, attr))

class AttrDictYamlLoader(yaml.Loader):
    """
    A YAML loader that loads mappings into attribute dictionaries.
    """

    def __init__(self, *args, **kwargs):
        yaml.Loader.__init__(self, *args, **kwargs)

        self.add_constructor(u'tag:yaml.org,2002:map', type(self).construct_yaml_map)

    def construct_yaml_map(self, node):
        data = AttrDict()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

def _expand_pattern(pattern):
    "expand variables in a search pattern with regular expressions"
    import versions
    import packages
    import rez_filesys as filesys
    if not pattern.startswith('/'):
        pattern = '/' + pattern
    pattern = re.escape(pattern)
    expansions = [('version', versions.EXACT_VERSION_REGSTR),
                  ('name', packages.PACKAGE_NAME_REGSTR),
                  ('search_path', '|'.join('(%s)' % p for p in filesys._g_syspaths))]
    for key, value in expansions:
        pattern = pattern.replace(r'\{%s\}' % key, '(%s)' % value)
    return pattern + '$'

def _filename_is_match(config_info, filename):
    pattern = config_info['pattern']
    if isinstance(pattern, basestring):
        pattern = re.compile(_expand_pattern(pattern))
        config_info['pattern'] = pattern
    return pattern.search(to_posixpath(filename))

#------------------------------------------------------------------------------
# Base Classes and Functions
#------------------------------------------------------------------------------

def load(stream, type):
    """
    return the metadata from a stream given the serialization "type".
    """
    if type == 'yaml':
        try:
            return yaml.load(stream, AttrDictYamlLoader) or {}
        except yaml.composer.ComposerError as err:
            if err.context == 'expected a single document in the stream':
                # automatically switch to multi-doc
                return yaml.load_all(stream, AttrDictYamlLoader)
            raise
    raise MetadataError("Unknown metadata storage type: %r" % type)

def load_file(filename):
    """
    read metadata from a file. determines the proper de-serialization
    routine to run based on file extension.
    """
    ext = os.path.splitext(filename)[1]
    # hack for info.txt. for now we force .txt to parse using yaml. this format
    # will be going away
    if ext == '.txt':
        ext = '.yaml'
    with open(filename, 'r') as f:
        return load(f, ext.strip('.'))

def register_config(config_version, resource_key, cls, path=None):
    """
    register a config file. this informs rez what the config file is used for,
    how to validate its data and optionally, where to find it relative to the
    rez search path.

    resource_key : str
        unique name used to identify the resource. when retrieving metadata from
        a file, the resource type can be automatically determined from the
        optional path string, or explicitly using the resource_key.
    cls : Metadata class
        class used to validate metadata
    path : str (optional)
        a string pattern identifying where the resource file resides relative to
        the rez search path
    """
    config_info = {}
    config_info['key'] = resource_key
    assert issubclass(cls, Metadata)
    config_info['class'] = cls
    if path:
        config_info['pattern'] = path
    _configs[config_version].append(config_info)

def get_config(config_version, filename, key=None):
    file_configs = _configs.get(config_version)
    if file_configs:
        for config_info in file_configs:
            if key and key == config_info['key']:
                return config_info['class'](filename)
            elif 'pattern' in config_info and _filename_is_match(config_info, filename):
                return config_info['class'](filename)
    raise MetadataError("Could not find registered metadata configuration for %r" % filename)

def list_registered_keys(config_version):
    return [info['key'] for info in _configs[config_version]]

class Metadata(object):
    """
    The Metadata class provides a means to validate the structure of hierarchical
    metadata.

    The STRUCTURE attribute defines a reference document which is compared
    against the metadata document passed to `validate()`. The reference document
    provided by the STRUCTURE attribute can either be a single document or a
    list of documents. If it is a list, the additional documents provide
    a subset of the original with alternate types for particular items.
    """
    SERIALIZER = 'yaml'
    # string showing a reference implementation of the file:
    STRUCTURE = None
    # list of required nodes:
    REQUIRED = ()
    # list of optional nodes which should not be stripped
    # when producing lightweight copy:
    PROTECTED = ()

    _refdocs = None

    def __init__(self, filename):
        self.filename = filename

    @classmethod
    def get_reference_docs(cls):
        if cls._refdocs is None:
            if cls.STRUCTURE is None:
                raise NotImplementedError("Configuration must provide a structure string: %r" % (cls))
            if isinstance(cls.STRUCTURE, basestring):
                docs = [cls.STRUCTURE]
            else:
                docs = cls.STRUCTURE
            # the dedent may not be safe for serializers other than yaml
            cls._refdocs = [load(textwrap.dedent(d), cls.SERIALIZER) for d in docs]
        return cls._refdocs

    def check_node(self, node, refnode, id='root'):
        """
        check a node against the reference node. checks type and existence.
        """
        if type(node) != type(refnode):
            yield (id, MetadataTypeError(self.filename, id, type(refnode), type(node)))
        else:
            if isinstance(refnode, dict):
                for key in refnode:
                    if key in node:
                        for res in self.check_node(node[key],
                                                   refnode[key],
                                                   id='%s.%s' % (id, key)):
                            yield res
                    elif key in self.REQUIRED:
                        yield (id, MetadataKeyError(self.filename, id))
                    else:
                        # add it to the dictionary
                        node[key] = None
            elif isinstance(refnode, list):
                refitem = refnode[0]
                for i, item in enumerate(node):
                    for res in self.check_node(item,
                                               refitem,
                                               id='%s[%s]' % (id, i)):
                        yield res
            yield (id, None)

    def validate_document_structure(self, doc, refdocs):
        prev_results = {}
        for refdoc in refdocs:
            curr_results = dict(self.check_node(doc, refdoc))
            # an id fails if all runs fail.
            for id, value in curr_results.iteritems():
                if id not in prev_results:
                    prev_results[id] = value
                elif value is not None and prev_results[id] is not None:
                    # failure
                    prev_results[id] = value
                else:
                    prev_results[id] = None
        failures = [val for id, val in prev_results.items() if val is not None]
        if failures:
            print "%d failures" % len(failures)
            raise failures[0]

    def validate(self, metadata):
        self.validate_document_structure(metadata,
                                         self.get_reference_docs())

    def strip(self, metadata):
        """
        remove non-protected data
        """
        remove = set(metadata.keys()).difference(self.REQUIRED + self.PROTECTED)
        for key in remove:
            metadata.pop(key, None)

#------------------------------------------------------------------------------
# Configurations
#------------------------------------------------------------------------------

class ReleaseInfo(Metadata):
    STRUCTURE = ('''\
        ACTUAL_BUILD_TIME : 0
        BUILD_TIME : 0
        USER : str
        SVN : str''')
    REQUIRED = ('ACTUAL_BUILD_TIME', 'BUILD_TIME', 'USER')

class BasePackageConfig_0(Metadata):
    STRUCTURE = ('''\
        config_version : 0
        uuid : str
        description : str
        version : str
        name : str
        help : str
        authors : [str]
        requires : [str]
        build_requires : [str]
        variants : [[str]]
        commands : [str]''',
        '''\
        commands: str''')
    REQUIRED = ('config_version', 'name')
    PROTECTED = ('requires', 'build_requires', 'variants', 'commands')

class VersionPackageConfig_0(BasePackageConfig_0):
    REQUIRED = ('config_version', 'name', 'version')

    def validate(self, metadata):
        # versions that look like floats will raise an error.
        # should we require these to be quoted in the yaml file?
        if 'version' in metadata:
            metadata['version'] = str(metadata['version'])
        Metadata.validate(self, metadata)
        import versions
        if not re.match(versions.EXACT_VERSION_REGSTR + '$', metadata['version']):
            raise MetadataValueError(self.filename, 'version', metadata['version'])

# class PackageConfig(VersionedMetadata):
#     VERSIONS = {0: PackageConfig0}

class PackageBuildConfig_0(VersionPackageConfig_0):
    """
    A package that is built with the intention to release is stricter about
    the existence of certain metadata values
    """
    REQUIRED = ('config_version', 'name', 'version', 'uuid', 'description', 'authors')


register_config(0,
                'version_package',
                VersionPackageConfig_0,
                path='{name}/{version}/package.yaml')

register_config(0,
                'versionless_package',
                BasePackageConfig_0,
                path='{name}/package.yaml')

register_config(0,
                'release_info',
                ReleaseInfo,
                path='{name}/{version}/.metadata/info.txt')

register_config(0,
                'built_package',
                PackageBuildConfig_0)

#------------------------------------------------------------------------------
# Main Entry Point
#------------------------------------------------------------------------------

def load_metadata(filename, strip=False, resource_key=None, min_config_version=0,
                  force_config_version=None):
    """
    Return the metadata stored in a file and validate it against a metadata
    configuration.

    Parameters
    ----------
    filename : str
        path to the file from which to load the metadata
    resource_key : str or None
        if set, determine validation of the metadata based on this key instead
        of based on the file path
    min_config_version : int
        the minimum config version required
    force_config_version : int or None
        used for legacy config files that do not store a configuration version
    """
    metadata = load_file(filename)
    if 'config_version' not in metadata:
        if force_config_version is not None:
            config_version = force_config_version
        else:
            raise MetadataKeyError(filename, 'config_version')
    else:
        config_version = metadata['config_version']
        if config_version < min_config_version:
            raise MetadataError('configuration version %d '
                                'is less than minimum requested: %d' % (config_version,
                                                                        min_config_version))
    config = get_config(config_version, filename, resource_key)
    if config is None:
        raise MetadataValueError(filename, 'config_version', metadata.config_version)
    config.validate(metadata)
    if strip:
        config.strip(metadata)
    return metadata





# Original code, left for easy reference for the time being:


# # TODO this class is too heavy
# class ConfigMetadata(object):
#     """
#     metafile. An incorrectly-formatted file will result in either a yaml exception (if
#     the syntax is wrong) or a MetadataError (if the content is wrong). An empty
#     metafile is acceptable, and is supported for fast integration of 3rd-party packages
#     """
# 
#     # file format versioning, only update this if the package.yamls have to change
#     # format in a way that is not backwards compatible
#     METAFILE_VERSION = 0
# 
#     def __init__(self, filename):
#         self.filename = filename
#         self.config_version = ConfigMetadata.METAFILE_VERSION
#         self.uuid = None
#         self.authors = None
#         self.description = None
#         self.name = None
#         self.version = None
#         self.help = None
#         self.requires = None
#         self.build_requires = None
#         self.variants = None
#         self.commands = None
# 
#         with open(filename) as f:
#             self.metadict = yaml.load(f.read()) or {}
# 
#         if self.metadict:
#             ###############################
#             # Common content
#             ###############################
# 
#             if (type(self.metadict) != dict):
#                 raise MetadataError("package metafile '" + self.filename + \
#                     "' contains non-dictionary root node")
# 
#             # config_version
#             self.config_version = self._get_int("config_version",
#                                                       required=True)
# 
#             if (self.config_version < 0) or (self.config_version > ConfigMetadata.METAFILE_VERSION):
#                 raise MetadataError("package metafile '" + self.filename + \
#                     "' contains invalid config version '" + str(self.config_version) + "'")
# 
#             self.uuid            = self._get_str("uuid")
#             self.description     = self._get_str("description")
#             self.version         = self._get_str("version")
#             self.name             = self._get_str("name")
#             self.help             = self._get_str("help")
#             self.authors        = self._get_list("authors", subtype=str)
# 
#             # config-version-specific content
#             if (self.config_version == 0):
#                 self.load_0();
# 
#     def _get_list(self, label, subtype=None, required=False):
#         value = self.metadict.get(label)
#         if value is None:
#             if required:
#                 raise MetadataError("package metafile '%s' "
#                                           "is missing required '%s' entry" %
#                                           (self.filename, label))
#             return None
# 
#         if not isinstance(value, list):
#             raise MetadataError("package metafile '%s' "
#                                       "contains non-list '%s' entry" %
#                                       (self.filename, label))
#         if len(value) == 0:
#             return None
#         elif subtype is not None:
#             if not isinstance(value[0], subtype):
#                 raise MetadataError("package metafile '%s' "
#                                           "contains non-%s '%s' entries" %
#                                           (self.filename, subtype.__name__, label))
#         return value
# 
#     def _get_str(self, label, required=False):
#         value = self.metadict.get(label)
#         if value is None:
#             if required:
#                 raise MetadataError("package metafile '%s' "
#                                           "is missing required '%s' entry" %
#                                           (self.filename, label))
#             return None
#         return str(value).strip()
# 
#     def _get_int(self, label, required=False):
#         value = self.metadict.get(label)
#         if value is None:
#             if required:
#                 raise MetadataError("package metafile '%s' "
#                                           "is missing required '%s' entry" %
#                                           (self.filename, label))
#             return None
# 
#         try:
#             return int(value)
#         except (ValueError, TypeError):
#             raise MetadataError("package metafile '%s' "
#                                       "contains non-int '%s' entry" %
#                                       (self.filename, label))
# 
#     def delete_nonessentials(self):
#         """
#         Delete everything not needed for package resolving.
#         """
#         if self.uuid:
#             del self.metadict["uuid"]
#             self.uuid = None
#         if self.description:
#             del self.metadict["description"]
#             self.description = None
#         if self.help:
#             del self.metadict["help"]
#             self.help = None
#         if self.authors:
#             del self.metadict["authors"]
#             self.authors = None
# 
#     def get_requires(self, include_build_reqs = False):
#         """
#         Returns the required package names, if any
#         """
#         if include_build_reqs:
#             reqs = []
#             # add build-reqs beforehand since they will tend to be more specifically-
#             # versioned, this will speed up resolution times
#             if self.build_requires:
#                 reqs += self.build_requires
#             if self.requires:
#                 reqs += self.requires
# 
#             if len(reqs) > 0:
#                 return reqs
#             else:
#                 return None
#         else:
#             return self.requires
# 
#     def get_build_requires(self):
#         """
#         Returns the build-required package names, if any
#         """
#         return self.build_requires
# 
#     def get_variants(self):
#         """
#         Returns the variants, if any
#         """
#         return self.variants
# 
#     def get_commands(self):
#         """
#         Returns the commands, if any
#         """
#         return self.commands
# 
#     def get_string_replace_commands(self, version, base, root):
#         """
#         Get commands with string replacement
#         """
#         if self.commands:
# 
#             vernums = version.split('.') + [ '', '' ]
#             major_version = vernums[0]
#             minor_version = vernums[1]
#             user = os.getenv("USER", "UNKNOWN_USER")
# 
#             new_cmds = []
#             for cmd in self.commands:
#                 cmd = cmd.replace("!VERSION!", version)
#                 cmd = cmd.replace("!MAJOR_VERSION!", major_version)
#                 cmd = cmd.replace("!MINOR_VERSION!", minor_version)
#                 cmd = cmd.replace("!BASE!", base)
#                 cmd = cmd.replace("!ROOT!", root)
#                 cmd = cmd.replace("!USER!", user)
#                 new_cmds.append(cmd)
#             return new_cmds
#         return None
# 
#     def load_0(self):
#         """
#         Load config_version=0
#         """
#         self.requires = self._get_list("requires", subtype=str)
#         self.build_requires = self._get_list("build_requires", subtype=str)
#         self.variants = self._get_list("variants", subtype=list)
#         try:
#             self.commands = self._get_list("commands", subtype=str)
#         except MetadataError:
#             # allow use of yaml multi-line strings
#             self.commands = [x for x in self._get_str("commands").split('\n') if x]



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
