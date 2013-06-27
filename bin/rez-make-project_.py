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

TEMPLATE_CONFIG_DIR = 'TEMPLATE_CONFIG'
VARIANT_DIR = '_VARIANT_'
TEMPLATE_CONFIG_FILE = 'TEMPLATE_CONFIG.yaml'
template_path = "%s/template/project_types" % (os.getenv("REZ_PATH"))
_project_types = [projDir for projDir in os.listdir(template_path) if os.path.isdir('%s/%s' % (template_path, projDir))]
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

_cmake_templates = {
"BIN_CMAKE_CODE": \
    """
    file(GLOB_RECURSE bin_files "bin/*")
    rez_install_files(
        ${bin_files}
        DESTINATION .
        EXECUTABLE
    )
    """,

"DOXYGEN_CMAKE_CODE": \
    """
    include(RezInstallDoxygen)
    file(GLOB_RECURSE doc_files "docs/*")

    rez_install_doxygen(
        doc
        FILES %(FILES)s ${doc_files}
        DESTINATION doc
        %(DOXYPY)s

        # remove this once your docs have stabilised, then they will only be built and
        # installed when you're performing a central install (ie a rez-release).
        FORCE
    )
    """
}

###########################################################################
# functions
###########################################################################

def _mkdir(dir):
    if not os.path.exists(dir):
        print "making %s..." % os.path.abspath(dir)
        os.mkdir(dir)

def _copy_structure(template_dir, cmake_code_filename, _project_types, variant=''):
    for root, dirs, files in os.walk(template_dir):
        if root != '%s/%s' % (template_dir, TEMPLATE_CONFIG_DIR):
            dest_root = _expand_path(root.replace(template_dir, cwd))
            for dir in dirs:
                if dir != TEMPLATE_CONFIG_DIR:
                    dest_dir = _expand_path(os.path.join(dest_root, dir))
                    dest_dir = _expand_variant_path(dest_dir, variant=variant)
                    _mkdir(dest_dir)

            for file in files:
                if file != cmake_code_filename and file != TEMPLATE_CONFIG_FILE and file != '.gitignore':
                    fpath = os.path.join(root, file)
                    f = open(fpath, 'r')
                    s = f.read()
                    f.close()

                    if file == 'CMakeLists.txt':
                        s += _add_to_empty_cmakelists(_project_types)
                    # do string replacement, and remove extraneous blank lines
                    s = _expand(s)
                    while "\n\n\n" in s:
                        s = s.replace("\n\n\n", "\n\n")

                    dest_fpath = _expand(os.path.join(dest_root, file))
                    if not os.path.isfile(dest_fpath):
                        print "making %s..." % dest_fpath
                        f = open(dest_fpath, 'w')
                        f.write(s)
                        f.close()


def _create_str_repl(proj_name, proj_version, _project_types):
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

def _add_to_empty_cmakelists(_project_types):
    s = '\n'
    for proj_type in _project_types:
        utype = proj_type.upper()
        ustring = '%%(%s_CMAKE_CODE)s' % (utype)
        s += '%s\n' % ustring
    return s

def _expand(s):
    return s % str_repl


def _expand_path(s):
    s = s.replace("_tokstart_", "%(")
    s = s.replace("_tokend_", ")s")
    return _expand(s)

def _expand_variant_path(s, variant=''):
    s = s.replace(VARIANT_DIR, variant)
    return s


def _gen_list(label, vals, variant=False):
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
    f = open(configFile, 'r')
    config = yaml.load(f)
    f.close()
    return config


def _read_cmake_code(cmake_code_filepath):
    s = ''
    if os.path.isfile(cmake_code_filepath):
        f = open(cmake_code_filepath, 'r')
        for line in f.readlines():
            s += line
        f.close()
    return s


###########################################################################
# cmdlin
###########################################################################
usage = "usage: rez-make-project <name> <version>"
proj_types_str = str(',').join(_project_types)

p = OptionParser(usage=usage)
p.add_option("--type", dest="type", type="string", default="empty", \
             help="Project type - one of [%s]. (default: empty)" % proj_types_str)
p.add_option("--tools", dest="tools", type="string", default="", \
             help="Optional set of programs to create, comma-separated.")
p.add_option("--variants", dest="variants", type="string", default="", \
             help="Optional set of variant folders to create, comma-separated.")
p.add_option("--template_folder", dest="template_location", type="string", default="", \
             help="folder containing custom templates.")

(opts, args) = p.parse_args()

is_custom_template = False
_custom_project_types = []
if opts.template_location:
    if os.path.isdir(opts.template_location):
        _custom_project_types = [custom_projDir for custom_projDir in os.listdir(opts.template_location) if os.path.isdir('%s/%s' % (opts.template_location, custom_projDir))]
        if _custom_project_types:
            _project_types += _custom_project_types
            proj_types_str = str(',').join(_project_types)
            if opts.type in _custom_project_types:
                is_custom_template = True

if opts.type not in _project_types:
    p.error("'%s' is not a recognised project type. Choose one of: [%s]" \
            % (opts.type, proj_types_str))

if len(args) != 2:
    p.error("Wrong argument count.")

proj_name = args[0]
proj_version = args[1]



## GET PROPERTIES FROM TEMPLATE CONFIG YAML FOR THE PROJECT TYPE WE ARE BUILDING

if not is_custom_template:
    projConfigFile = "%s/template/project_types/%s/%s/%s" % (os.getenv("REZ_PATH"), opts.type, TEMPLATE_CONFIG_DIR, TEMPLATE_CONFIG_FILE)
else:
    projConfigFile = "%s/%s/%s/%s" % (opts.template_location, opts.type, TEMPLATE_CONFIG_DIR, TEMPLATE_CONFIG_FILE)

proj_config = _read_config(projConfigFile)


_project_template_deps = {'%s' % opts.type: []}
if proj_config.has_key('templateDependencies'):
    _project_template_deps = {'%s' % opts.type: proj_config['templateDependencies']}

_project_requires = {'%s' % opts.type: []}
if proj_config.has_key('requires'):
    _project_requires = {'%s' % opts.type: proj_config['requires']}

_project_build_requires = {'%s' % opts.type: []}
if proj_config.has_key('buildRequires'):
    _project_build_requires = {'%s' % opts.type: proj_config['buildRequires']}

_project_commands = {'%s' % opts.type: []}
if proj_config.has_key('commands'):
    _project_commands = {'%s' % opts.type: proj_config['commands']}

proj_types = [opts.type]
proj_types += _project_template_deps[opts.type] or []

###########################################################################
# query system
###########################################################################
if "doxygen" in proj_types:
    doxygen_support = True
    doxypy_support = True
    doxygen_file_types = []
    string_repl_d = {"DOXYPY": ""}

    p = sp.Popen("rez-which doxygen", shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    p.communicate()
    if p.returncode != 0:
        if "doxygen" in _project_build_requires[opts.type]:
            _project_build_requires[opts.type].remove("doxygen")
            doxygen_support = False

    if doxygen_support and "doxygen" in _project_build_requires[opts.type] and "python" in proj_types:
        p = sp.Popen("rez-which doxypy", shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
        p.communicate()
        if p.returncode == 0:
            _project_build_requires[opts.type]["doxygen"].append("doxypy")
            string_repl_d["DOXYPY"] = "DOXYPY"
            doxygen_file_types.append("py_files")
        else:
            print >> sys.stderr, "Skipped doxygen python support, 'doxypy' package not found!"
            doxypy_support = False

    doxy_files_str = str(' ').join([("${%s}" % x) for x in doxygen_file_types])
    string_repl_d["FILES"] = doxy_files_str
    doxy_cmake_code_filename = "doxygen_cmake_code"
    doxy_cmake_code_filepath = "%s/template/project_types/doxygen/%s/%s" % (os.getenv("REZ_PATH"), TEMPLATE_CONFIG_DIR, doxy_cmake_code_filename)
    doxyCode = _read_cmake_code(doxy_cmake_code_filepath)
    code = doxyCode % string_repl_d
    _cmake_templates["DOXYGEN_CMAKE_CODE"] = code



###########################################################################
# create files and dirs
###########################################################################

print "creating files and directories for %s project %s-%s..." % \
	(opts.type, proj_name, proj_version)

str_repl = _create_str_repl(proj_name, proj_version, _project_types)

requires = _project_requires[opts.type]
build_requires = _project_build_requires[opts.type]
commands = _project_commands[opts.type]
tools = []
variants = []

# insert tools
if opts.tools:
    tools = opts.tools.strip().split(',')
    str_repl["TOOLS"] = _gen_list("tools", tools, variant=False)
    str_repl["BIN_CMAKE_CODE"] = bin_cmake_code_template
    commands.append("export PATH=$PATH:!ROOT!/bin")

# insert variants from cmdline arg
if opts.variants:
    variants = opts.variants.strip().split(',')
    str_repl["VARIANTS"] = _gen_list("variants", variants, variant=True)


# copy and string-replace the templates
for proj_type in proj_types:
    utype = proj_type.upper()

    cmake_code_tok = "%s_CMAKE_CODE" % utype
    cmake_code_filename = "%s_cmake_code" % proj_type

    if proj_type not in _custom_project_types:
        cmake_code_filepath = "%s/template/project_types/%s/%s/%s" % (os.getenv("REZ_PATH"), proj_type, TEMPLATE_CONFIG_DIR, cmake_code_filename)
    else:
        cmake_code_filepath = "%s/%s/%s/%s" % (opts.template_location, proj_type, TEMPLATE_CONFIG_DIR, cmake_code_filename)
    if str_repl.has_key(cmake_code_tok):
        str_repl[cmake_code_tok] += _read_cmake_code(cmake_code_filepath)
    else:
        str_repl[cmake_code_tok] = _read_cmake_code(cmake_code_filepath)

    if proj_type == "doxygen":
        str_repl["HELP"] = "help: %s file://!ROOT!/doc/html/index.html" % browser

    if proj_type in _project_requires[opts.type]:
        if proj_type not in requires:
            requires.append(proj_type)
    if proj_type in _project_build_requires[opts.type]:
        build_requires.append(proj_type)

    str_repl["COMMANDS"] = _gen_list("commands", commands, variant=False)
    str_repl["REQUIRES"] = _gen_list("requires", requires, variant=False)
    str_repl["BUILD_REQUIRES"] = _gen_list("build_requires", build_requires, variant=False)

    if proj_type not in _custom_project_types:
        template_dir = "%s/template/project_types/%s" % (os.getenv("REZ_PATH"), proj_type)
    else:
        template_dir = "%s/%s" % (opts.template_location, proj_type)
    if not os.path.exists(template_dir):
        print >> sys.stderr, "Internal error - path %s not found." % template_dir
        sys.exit(1)

    # create the actual structure
    if variants:
        for variant in variants:
            _copy_structure(template_dir, cmake_code_filename, _project_types, variant=variant)
    else:
        _copy_structure(template_dir, cmake_code_filename, _project_types, variant='')



# add programs, if applicable
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
