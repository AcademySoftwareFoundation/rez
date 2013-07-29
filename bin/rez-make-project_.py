#!/tools/shed/opensource/python/2.7.3/payload/bin/python

from optparse import OptionParser
import subprocess as sp
import sys
import os
import os.path
import shutil
import uuid
import yaml

###########################################################################
# vars
###########################################################################
# Define global vars
TEMPLATE_CONFIG_DIR = 'TEMPLATE_CONFIG'
VARIANT_DIR = '_VARIANT_'
TEMPLATE_CONFIG_FILE = 'TEMPLATE_CONFIG.yaml'
TEMPLATE_PATH = "%s/template/project_types" % (os.getenv("REZ_PATH"))
_project_types = [projDir for projDir in os.listdir(TEMPLATE_PATH) if os.path.isdir('%s/%s' % (TEMPLATE_PATH, projDir))]
cwd = os.getcwd()
browser = os.getenv("BROWSER") or "firefox"

bin_cmake_code_template = \
"""
file(GLOB_RECURSE bin_files "bin/*")
rez_install_files(
    ${bin_files}
    DESTINATION .
    EXECUTABLE
)
"""

###########################################################################
# functions
###########################################################################

def _mkdir(directory):
    """
    Function to create a directory.
    :param directory: directory to make
    :type directory: str
    """
    if not os.path.exists(directory):
        print "making %s..." % os.path.abspath(directory)
        os.mkdir(directory)

def _copy_structure(template_dir, cmake_code_filename, _project_types, variant=''):
    """
    Function to copy the directory structure from the project template to the cwd.
    Creating the CMakeLists.txt and package.yaml files.

    :param template_dir: path to project templates
    :type template_dir: str

    :param cmake_code_filename: name of the txt file containing the cmake code
    :type cmake_code_filename: str

    :param _project_types: default list of project types
    :type _project_types: list

    :param variant: if this is a variant specify which one eg 2012
    :type variant: str
    """
    for root, dirs, files in os.walk(template_dir):
        if root != '%s/%s' % (template_dir, TEMPLATE_CONFIG_DIR):
            dest_root = _expand_path(root.replace(template_dir, cwd))
            for directory in dirs:
                if directory != TEMPLATE_CONFIG_DIR:
                    dest_dir = _expand_path(os.path.join(dest_root, directory))
                    dest_dir = _expand_variant_path(dest_dir, variant=variant)
                    _mkdir(dest_dir)

            for fileX in files:
                if fileX != cmake_code_filename and fileX != TEMPLATE_CONFIG_FILE and fileX != '.gitignore':
                    fpath = os.path.join(root, fileX)
                    f = open(fpath, 'r')
                    s = f.read()
                    f.close()

                    if fileX == 'CMakeLists.txt':
                        s += _build_cmakelists_keys(_project_types)
                    # do string replacement, and remove extraneous blank lines
                    s = _expand(s)
                    while "\n\n\n" in s:
                        s = s.replace("\n\n\n", "\n\n")

                    dest_fpath = _expand(os.path.join(dest_root, fileX))
                    if not os.path.isfile(dest_fpath):
                        print "making %s..." % dest_fpath
                        f = open(dest_fpath, 'w')
                        f.write(s)
                        f.close()


def _create_str_repl(proj_name, proj_version, _project_types):
    """
    Function that returns a dictionary of attrs for the project.

    :param proj_name: name of the project
    :type proj_name: str

    :param proj_version: version of the project
    :type proj_version: str

    :param _project_types: default list of project types
    :type _project_types: list

    :returns: str_repl
    :rtype: dict
    """
    str_repl = {
	"NAME":						proj_name,
	"VERSION":					proj_version,
	"USER":						os.getenv("USER"),
	"UUID":						str(uuid.uuid4()),
	"REZ_PATH":					os.getenv("REZ_PATH"),
	"BIN_CMAKE_CODE":			'',
	"COMMANDS":					'',
	"TOOLS":					'',
	"REQUIRES":					'',
	"BUILD_REQUIRES":			'',
	"HELP":						'',
    "VARIANTS":                 ''
    }
    for proj_type in _project_types:
        utype = proj_type.upper()
        key = '%s_CMAKE_CODE' % utype
        str_repl[key] = ''
    return str_repl

def _build_cmakelists_keys(_project_types):
    """
    Function to build a string of CMAKE_CODE keys which can be replaced with the corresponding values in the str_repl dict

    :param _project_types: default list of project types
    :type _project_types: list

    :returns: s
    :rtype: str
    """
    s = '\n'
    for proj_type in _project_types:
        utype = proj_type.upper()
        ustring = '%%(%s_CMAKE_CODE)s' % (utype)
        s += '%s\n' % ustring
    return s

def _expand(s):
    """
    Function to replace the strings with values from the str_repl dictionary

    :param s: string to modify
    :type s: str

    :returns: s
    :rtype: str
    """
    return s % str_repl


def _expand_path(s):
    """
    Function to replace template directory names.
    Replaces _tokstart_ with %( and _tokend_ )s

    :param s: string to modify
    :type s: str

    :returns: s
    :rtype: str
    """
    s = s.replace("_tokstart_", "%(")
    s = s.replace("_tokend_", ")s")
    return _expand(s)

def _expand_variant_path(s, variant=''):
    """
    Function to replace template variant directory with the variant name.
    Replaces VARIANT_DIR with the variant

    :param s: string to modify
    :type s: str

    :param variant: variant
    :type variant: str

    :returns: s
    :rtype: str
    """
    s = s.replace(VARIANT_DIR, variant)
    return s


def _gen_list(label, vals, variant=False):
    """
    Function to generate a string in the syntax of yaml lists

    :param label: label of the list
    :type label: str

    :param vals: list of values
    :type vals: list

    :param variant: if this is for variants
    :type variant: bool

    :returns: s
    :rtype: str
    """
    s = ''
    if vals:
        s += label + ":\n"
        for val in vals:
            if not variant:
                s += "- %s\n" % val
            else:
                s += "- [ %s ]\n" % val
    return s


def _read_config(configFile):
    """
    Function to read a template config yaml file and return it as dictionary

    :param configFile: path to the config file
    :type configFile: str

    :returns: config
    :rtype: dict
    """
    f = open(configFile, 'r')
    config = yaml.load(f)
    f.close()
    return config


def _read_cmake_code(proj, cmake_code_filename, template_location):
    """
    Function to read the cmake code text file and return it as a string.

    :param proj: name of the project template
    :type proj: str

    :param cmake_code_filename: name of the cmake code text file
    :type cmake_code_filename: str

    :param template_location: path to custom templates
    :type template_location: str

    :returns: s
    :rtype: str
    """
    cmake_code_filepath = "%s/%s/%s/%s" % (TEMPLATE_PATH, proj, TEMPLATE_CONFIG_DIR, cmake_code_filename)
    if not os.path.isfile(cmake_code_filepath):
        cmake_code_filepath = "%s/%s/%s/%s" % (template_location, proj, TEMPLATE_CONFIG_DIR, cmake_code_filename)

    s = ''
    if os.path.isfile(cmake_code_filepath):
        f = open(cmake_code_filepath, 'r')
        for line in f.readlines():
            s += line
        f.close()
    return s

def _query_doxygen(proj_types, _project_build_requires):
    """
    Function to query if doxygen is available.
    Return the required doxygn cmake code and build requirements

    :param proj_types: list of project templates along with dependent templates
    :type proj_types: list

    :param _project_build_requires: list of project build requirement
    :type _project_build_requires: list

    :returns: code
    :rtype: str

    :returns: _project_build_requires
    :rtype: list
    """
    doxygen_support = True
    doxypy_support = True
    doxygen_file_types = []
    string_repl_d = {"DOXYPY": ""}

    p = sp.Popen("rez-which doxygen", shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    p.communicate()
    p.returncode = 0
    if p.returncode != 0:
        if "doxygen" in _project_build_requires:
            _project_build_requires.remove("doxygen")
            doxygen_support = False

    if doxygen_support and "python" in proj_types:
        p = sp.Popen("rez-which doxypy", shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
        p.communicate()
        p.returncode = 0
        if p.returncode == 0:
            if "doxypy" not in _project_build_requires:
                _project_build_requires.append("doxypy")
            string_repl_d["DOXYPY"] = "DOXYPY"
            doxygen_file_types.append("py_files")
        else:
            print >> sys.stderr, "Skipped doxygen python support, 'doxypy' package not found!"
            doxypy_support = False

    doxy_files_str = str(' ').join([("${%s}" % x) for x in doxygen_file_types])
    string_repl_d["FILES"] = doxy_files_str
    doxy_cmake_code_filename = "doxygen_cmake_code"
    doxyCode = _read_cmake_code("doxygen", doxy_cmake_code_filename, '')
    code = doxyCode % string_repl_d

    return code, _project_build_requires

def _get_config(proj, is_custom_template):
    """
    Function to get the project template configuration as a dictionary.

    :param proj: name of the project template
    :type proj: str

    :param is_custom_template: if the project template is a custom template
    :type is_custom_template: bool

    :returns: proj_config
    :rtype: dict
    """
    if not is_custom_template:
        projConfigFile = "%s/%s/%s/%s" % (TEMPLATE_PATH, proj, TEMPLATE_CONFIG_DIR, TEMPLATE_CONFIG_FILE)
    else:
        projConfigFile = "%s/%s/%s/%s" % (opts.template_location, proj, TEMPLATE_CONFIG_DIR, TEMPLATE_CONFIG_FILE)
    proj_config = {}
    if proj != 'empty':
        proj_config = _read_config(projConfigFile)

    return proj_config


def _reorder_proj_list(proj_list):
    if "doxygen" in proj_list:
        index = proj_list.index("doxygen")
        doxy = proj_list.pop(index)
        proj_list.append(doxy)

    if "empty" in proj_list:
        index = proj_list.index("empty")
        empty = proj_list.pop(index)
        proj_list.append(empty)

    return proj_list



###########################################################################
# cmdlin
###########################################################################
usage = "usage: rez-make-project <name> <version>"
proj_types_str = str(',').join(_project_types)

p = OptionParser(usage=usage)
p.add_option("--type", dest="type", type="string", default="empty", \
             help="Project types -  [%s]. (default: empty).Can be multiple comma-separated" % proj_types_str)
p.add_option("--tools", dest="tools", type="string", default="", \
             help="Optional set of programs to create, comma-separated.")
p.add_option("--variants", dest="variants", type="string", default="", \
             help="Optional set of variant folders to create, comma-separated.")
p.add_option("--template_folder", dest="template_location", type="string", default="", \
             help="folder containing custom templates.")

(opts, args) = p.parse_args()

## 1. get all the project templates specified with --type and determine if any of them are custom templates
create_proj_types = {}
for ptype in opts.type.split(','):
    create_proj_types[ptype] = {'is_custom_template' : False}

is_custom_template = False
_custom_project_types = []
if opts.template_location:
    if os.path.isdir(opts.template_location):
        _custom_project_types = [custom_projDir for custom_projDir in os.listdir(opts.template_location) if os.path.isdir('%s/%s' % (opts.template_location, custom_projDir))]
        if _custom_project_types:
            _project_types += _custom_project_types
            proj_types_str = str(',').join(_project_types)
            for ptype in create_proj_types:
                if ptype in _custom_project_types:
                    create_proj_types[ptype]['is_custom_template'] = True

## 2. error check
for ptype in create_proj_types:
    if ptype not in _project_types:
        p.error("'%s' is not a recognised project type. Choose one of: [%s]" \
                % (ptype, proj_types_str))

if len(args) != 2:
    p.error("Wrong argument count.")

proj_name = args[0]
proj_version = args[1]

## 3. get the project template configs for each of the project types specified with --type
proj_config = {}
proj_types = []
for ptype in create_proj_types:
    proj_types.append(ptype)
    proj_config[ptype] = _get_config(ptype, create_proj_types[ptype]['is_custom_template'])
    if proj_config[ptype].has_key('templateDependencies'):
        proj_types += proj_config[ptype]['templateDependencies']
proj_types = list(set(proj_types))

## 4. reorganize the master project types list so that doxygen and empty project types are always at the end since we want these to be processed last.
# _project_types = _reorder_proj_list(_project_types)
# proj_types = _reorder_proj_list(proj_types)
if "doxygen" in _project_types:
    index = _project_types.index("doxygen")
    doxy = _project_types.pop(index)
    _project_types.append(doxy)

if "empty" in _project_types:
    index = _project_types.index("empty")
    empty = _project_types.pop(index)
    _project_types.append(empty)

###########################################################################
# create files and dirs
###########################################################################

print "creating files and directories for %s project %s-%s..." % \
	(opts.type, proj_name, proj_version)

## 5. create variables. str_repl is a dictionary with keys whose values get built and finally used to replace the strings in the cmake & package.yaml files
str_repl = _create_str_repl(proj_name, proj_version, _project_types)

tools = []
variants = []
_project_requires = []
_project_build_requires = []
_project_commands = []

# insert tools
if opts.tools:
    tools = opts.tools.strip().split(',')
    str_repl["TOOLS"] = _gen_list("tools", tools, variant=False)
    str_repl["BIN_CMAKE_CODE"] = bin_cmake_code_template
    _project_commands.append("export PATH=$PATH:!ROOT!/bin")

# insert variants from cmdline arg
if opts.variants:
    variants = opts.variants.strip().split(',')
    str_repl["VARIANTS"] = _gen_list("variants", variants, variant=True)

## 6. For each project template we'll use add to the str_repl dictionary and finally create the dirs/files
for proj_type in proj_types:
    if proj_type not in _custom_project_types:
        template_dir = "%s/%s" % (TEMPLATE_PATH, proj_type)
    else:
        template_dir = "%s/%s" % (opts.template_location, proj_type)
    if not os.path.exists(template_dir):
        print >> sys.stderr, "Internal error - path %s not found." % template_dir
        sys.exit(1)

    utype = proj_type.upper()

    if proj_type != 'empty':
        proj_type_config = proj_config[proj_type]

        ## add to the requires list of the main project from dependencies
        if proj_type_config.has_key('requires'):
            for req in proj_type_config['requires']:
                if req not in _project_requires:
                    _project_requires.append(req)

        if proj_type_config.has_key('buildRequires'):
            for build_req in proj_type_config['buildRequires']:
                if build_req not in _project_build_requires:
                    _project_build_requires.append(build_req)

        if proj_type_config.has_key('commands'):
            for command in proj_type_config['commands']:
                if command not in _project_commands:
                    _project_commands.append(command)

    cmake_code_tok = "%s_CMAKE_CODE" % utype
    cmake_code_filename = "%s_cmake_code" % proj_type

    if proj_type == 'doxygen':
        code, _project_build_requires = _query_doxygen(proj_types, _project_build_requires)
    else:
        code = _read_cmake_code(proj_type, cmake_code_filename, opts.template_location)
    if str_repl.has_key(cmake_code_tok):
        str_repl[cmake_code_tok] += code
    else:
        str_repl[cmake_code_tok] = code

    if proj_type == "doxygen":
        str_repl["HELP"] = "help: %s file://!ROOT!/doc/html/index.html" % browser

    str_repl["COMMANDS"] = _gen_list("commands", _project_commands, variant=False)
    str_repl["REQUIRES"] = _gen_list("requires", _project_requires, variant=False)
    str_repl["BUILD_REQUIRES"] = _gen_list("build_requires", _project_build_requires, variant=False)

    # create the actual structure
    if variants:
        for variant in variants:
            _copy_structure(template_dir, cmake_code_filename, _project_types, variant=variant)
    else:
        _copy_structure(template_dir, cmake_code_filename, _project_types, variant='')

## 7. add programs, if applicable
if tools:
    shebang = '#!/bin/bash'
    if opts.type == "python":
        shebang = "#!/usr/bin/env python"
    _mkdir("./bin")

    for tool in tools:
        path = os.path.join("./bin", tool)
        print "creating %s..." % path
        f = open(path, 'w')
        f.write(shebang + '\n')
        f.close()
