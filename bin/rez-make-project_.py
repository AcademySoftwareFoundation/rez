#!!REZ_PYTHON_BINARY!

from optparse import OptionParser
import sys
import os
import os.path
import shutil
import uuid


bin_cmake_code_template = \
"""
file(GLOB_RECURSE bin_files "bin/*")
rez_install_files(
	${bin_files}
    DESTINATION .
    EXECUTABLE
)
"""


def _mkdir(dir):
	if not os.path.exists(dir):
		print "making %s..." % dir
		os.mkdir(dir)


_project_types = [
	"python"
]

_project_deps = {
	"python":	["doxygen"]
}


usage = "usage: rez-make-project <name> <version>"

p = OptionParser(usage=usage)
p.add_option("--type", dest="type", type="string", default="", \
    help="Project type - one of (%s)" % str(',').join(_project_types))
p.add_option("--tools", dest="tools", type="string", default="", \
    help="Optional set of programs to create, comma-separated.")

(opts, args) = p.parse_args()

if not opts.type:
	p.error("Need to specify a project type.")

if len(args) != 2:
	p.error("Wrong argument count.")

proj_name = args[0]
proj_version = args[1]
print "Creating files and directories for %s project %s-%s..." % (opts.type, proj_name, proj_version)

proj_types = [opts.type]
proj_types += _project_deps[opts.type] or []


# copy and string-replace the templates
for proj_type in proj_types:
	template_dir = "%s/template/project_types/%s" % (os.getenv("REZ_PATH"), proj_type)
	if not os.path.exists(template_dir):
		print >> sys.stderr, "Internal error - path %s not found." % template_dir
		sys.exit(1)

	# copy template files and directories, doing string replacement along the way
	str_repl = {
		"NAME":						proj_name,
		"VERSION":					proj_version,
		"USER":						os.getenv("USER"),
		"UUID":						str(uuid.uuid4()),
		"REZ_PATH":					os.getenv("REZ_PATH"),
		"BROWSER":					os.getenv("BROWSER") or "firefox",
		"BIN_CMAKE_CODE":			'',
		"BIN_PATH_EXPORT_CMD":		'',
		"TOOLS_YAML":				''
	}

	tools = []
	if opts.tools:
		tools = opts.tools.strip().split(',')
		tools_yaml = "tools:"
		for tool in tools:
			tools_yaml += "\n- %s" % tool

		str_repl["TOOLS_YAML"] = tools_yaml
		str_repl["BIN_CMAKE_CODE"] = bin_cmake_code_template
		str_repl["BIN_PATH_EXPORT_CMD"] = "- export PATH=$PATH:!ROOT!/bin"

	def _expand(s):
		return s % str_repl

	def _expand_path(s):
		s = s.replace("_tokstart_", "%(")
		s = s.replace("_tokend_", ")s")
		return _expand(s)

	cwd = os.getcwd()

	for root, dirs, files in os.walk(template_dir):
		dest_root = _expand_path(root.replace(template_dir, cwd))
		for dir in dirs:
			dest_dir = _expand_path(os.path.join(dest_root, dir))
			_mkdir(dest_dir)

		for file in files:
			fpath = os.path.join(root, file)
			f = open(fpath, 'r')
			s = f.read()
			f.close()
			
			s = _expand(s)
			dest_fpath = _expand(os.path.join(dest_root, file))
			print "making %s..." % dest_fpath
			f = open(dest_fpath, 'w')
			f.write(s)
			f.close()


# add programs, if applicable
if tools:
	shebang = ''
	if opts.type == "python":
		shebang = "#!/usr/bin/env me-python"
	_mkdir("./bin")

	for tool in tools:
		path = os.path.join("./bin", tool)
		f = open(path, 'w')
		f.write(shebang + '\n')
		f.close()
