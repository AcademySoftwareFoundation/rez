"""
Rez configuration settings. Do not change this file.

Settings are determined in the following way (higher number means higher
precedence):

1) The setting is first read from this file;
2) The setting is then overridden if it is present in another settings file
   pointed at by the $REZ_CONFIG_FILE environment variable;
3) The setting is further overriden if it is present in $HOME/.rezconfig;
4) The setting is overridden again if the environment variable $REZ_XXX is
   present, where XXX is the uppercase version of the setting key. For example,
   "image_viewer" will be overriden by $REZ_IMAGE_VIEWER. List values can be
   separated either with "," or blank space. Dict values are in the form
   "k1:v1,k2:v2,kn:vn";
5) The setting can also be overriden by the environment variable $REZ_XXX_JSON,
   and in this case the string is expected to be a JSON-encoded value;
6) This is a special case applied only during a package build or release. In
   this case, if the package definition file contains a "config" section,
   settings in this section will override all others.

Note that in the case of plugin settings (anything under the "plugins" section
of the config), (4) and (5) do not apply.

Variable expansion can be used in configuration settings. The following
expansions are supported:
- Any property of the system object: Eg "{system.platform}" (see system.py)
- Any environment variable: Eg "${HOME}"

The following variables are provided if you are using rezconfig.py files:
- 'rez_version': The current version of rez.

Paths should use the path separator appropriate for the operating system
(based on Python's os.path.sep).  So for Linux paths, / should be used. On
Windows \ (unescaped) should be used.

Note: The comments in this file are extracted and turned into Wiki content. Pay
attention to the comment formatting and follow the existing style closely.
"""
import os


###############################################################################
# Paths
###############################################################################

### Do not move or delete this comment (__DOC_START__)

# The package search path. Rez uses this to find packages. A package with the
# same name and version in an earlier path takes precedence.
packages_path = [
    "~/packages",           # locally installed pkgs, not yet deployed
    "~/.rez/packages/int",  # internally developed pkgs, deployed
    "~/.rez/packages/ext",  # external (3rd party) pkgs, such as houdini, boost
]

# The path that Rez will locally install packages to when rez-build is used
local_packages_path = "~/packages"

# The path that Rez will deploy packages to when rez-release is used. For
# production use, you will probably want to change this to a site-wide location.
release_packages_path = "~/.rez/packages/int"

# Where temporary files go. Defaults to appropriate path depending on your
# system - for example, *nix distributions will probably set this to "/tmp". It
# is highly recommended that this be set to local storage, such as /tmp.
tmpdir = None

# Where temporary files for contexts go. Defaults to appropriate path depending
# on your system - for example, *nix distributions will probably set this to "/tmp".
# This is separate to 'tmpdir' because you sometimes might want to set this to an
# NFS location - for example, perhaps rez is used during a render and you'd like
# to store these tempfiles in the farm queuer's designated tempdir so they're
# cleaned up when the render completes.
context_tmpdir = None

# These are extra python paths that are added to sys.path **only during a build**.
# This means that any of the functions in the following list can import modules
# from these paths:
# * The *preprocess* function;
# * Any function decorated with @early - these get evaluated at build time.
#
# You can use this to provide common code to your package definition files during
# a build. To provide common code for packages to use at resolve time instead (for
# example, in a *commands* function) see the following
# *package_definition_python_path* setting.
#
package_definition_build_python_paths = []

# This is the directory from which installed packages can import modules. This
# is a way for packages to use shared code.
#
# This is NOT a standard path added to sys.path. Packages that use modules from
# within this directory need to explicitly name them. Furthermore, modules that
# a package uses are copied into that package's install - this ensures that the
# package remains standalone and that changes to the shared code will not break
# or alter existing package installs.
#
# Consider the setting:
#
#     package_definition_python_path = "/src/rezutils"
#
# Consider also the following package *commands* function:
#
#     @include("utils")
#     def commands():
#         utils.do_some_common_thing(this)
#
# This package will import the code from */src/rezutils/utils.py* (or more
# specifically, its copy of this sourcefile) and will bind it to the name *utils*.
#
# For further information, see
# [here](Package-Definition-Guide#sharing-code-across-package-definition-files).
#
package_definition_python_path = None


###############################################################################
# Extensions
###############################################################################

# Search path for rez plugins.
plugin_path = []

# Search path for bind modules. The *rez-bind* tool uses these modules to create
# rez packages that reference existing software already installed on the system.
bind_module_path = []


###############################################################################
# Caching
###############################################################################

# Cache resolves to memcached, if enabled. Note that these cache entries will be
# correctly invalidated if, for example, a newer package version is released that
# would change the result of an existing resolve.
resolve_caching = True

# Cache package file reads to memcached, if enabled. Updated package files will
# still be read correctly (ie, the cache invalidates when the filesystem
# changes).
cache_package_files = True

# Cache directory traversals to memcached, if enabled. Updated directory entries
# will still be read correctly (ie, the cache invalidates when the filesystem
# changes).
cache_listdir = True

# The size of the local (in-process) resource cache. Resources include package
# families, packages and variants. A value of 0 disables caching; -1 sets a cache
# of unlimited size. The size refers to the number of entries, not byte count.
resource_caching_maxsize = -1

# Uris of running memcached server(s) to use as a file and resolve cache. For
# example, the uri "127.0.0.1:11211" points to memcached running on localhost on
# its default port. Must be either null, or a list of strings.
memcached_uri = []

# Bytecount beyond which memcached entries are compressed, for cached package
# files (such as package.yaml, package.py). Zero means never compress.
memcached_package_file_min_compress_len = 16384

# Bytecount beyond which memcached entries are compressed, for cached context
# files (aka .rxt files). Zero means never compress.
memcached_context_file_min_compress_len = 1

# Bytecount beyond which memcached entries are compressed, for directory listings.
# Zero means never compress.
memcached_listdir_min_compress_len = 16384

# Bytecount beyond which memcached entries are compressed, for resolves. Zero
# means never compress.
memcached_resolve_min_compress_len = 1


###############################################################################
# Package Resolution
###############################################################################

# Packages that are implicitly added to all package resolves, unless the
# --no-implicit flag is used.
implicit_packages = [
    "~platform=={system.platform}",
    "~arch=={system.arch}",
    "~os=={system.os}",
]

# Override platform values from Platform.os and arch.
# This is useful as Platform.os might show different
# values depending on the availability of lsb-release on the system.
# The map supports regular expression e.g. to keep versions.
# Please note that following examples are not necessarily recommendations.
#
#     platform_map = {
#         "os": {
#             r"Scientific Linux-(.*)": r"Scientific-\1",                 # Scientific Linux-x.x -> Scientific-x.x
#             r"Ubuntu-14.\d": r"Ubuntu-14",                              # Any Ubuntu-14.x      -> Ubuntu-14
#             r'CentOS Linux-(\d+)\.(\d+)(\.(\d+))?': r'CentOS-\1.\2', '  # Centos Linux-X.Y.Z -> CentOS-X.Y
#         },
#         "arch": {
#             "x86_64": "64bit",                                          # Maps both x86_64 and amd64 -> 64bit
#             "amd64": "64bit",
#         },
#     }
platform_map = {}

# If true, then when a resolve graph is generated during a failed solve, packages
# unrelated to the failure are pruned from the graph. An "unrelated" package is
# one that is not a dependency ancestor of any packages directly involved in the
# failure.
prune_failed_graph = True

# Variant select mode. This determines which variants in a package are preferred
# during a solve. Valid options are:
# - version_priority: Prefer variants that contain higher versions of packages
#   present in the request;
# - intersection_priority: Prefer variants that contain the most number of
#   packages that are present in the request.
#
# As an example, suppose you have a package foo which has two variants:
#
#    variants = [
#        ["bar-3.0", "baz-2.1"],
#        ["bar-2.8", "burgle-1.0"]
#    ]
#
# if you do:
#
#    rez-env foo bar
#
# ...then, in either variant_select_mode, it will prefer the first variant,
# ["bar-3.0", "baz-2.1"], because it has a higher version of the first variant
# requirement (bar). However, if we instead do:
#
#    rez-env foo bar burgle
#
# ...we get different behavior. version_priority mode will still return
# ["bar-3.0", "baz-2.1"], because the first requirement's version is higher.
#
# However, intersection_priority mode will pick the second variant,
# ["bar-2.8", "burgle-1.0"], because it contains more packages that were in the
# original request (burgle).
variant_select_mode = "version_priority"

# Package filter. One or more filters can be listed, each with a list of
# exclusion and inclusion rules. These filters are applied to each package
# during a resolve, and if any filter excludes a package, that package is not
# included in the resolve. Here is a simple example:
#
#     package_filter:
#         excludes:
#         - glob(*.beta)
#         includes:
#         - glob(foo-*)
#
# This is an example of a single filter with one exclusion rule and one inclusion
# rule. The filter will ignore all packages with versions ending in '.beta',
# except for package 'foo' (which it will accept all versions of). A filter will
# only exclude a package iff that package matches at least one exclusion rule,
# and does not match any inclusion rule.
#
# Here is another example, which excludes all beta packages, and all packages
# except 'foo' that are released after a certain date. Note that in order to
# use multiple filters, you need to supply a list of dicts, rather than just a
# dict:
#
#     package_filter:
#     - excludes:
#       - glob(*.beta)
#     - excludes:
#       - after(1429830188)
#       includes:
#       - foo  # same as range(foo), same as glob(foo-*)
#
# This example shows why multiple filters are supported - with only one filter,
# it would not be possible to exclude all beta packages (including foo), but also
# exclude all packages after a certain date, except for foo.
#
# Following are examples of all the possible rules:
#
# example             | description
# --------------------|----------------------------------------------------
# glob(*.beta)        | Matches packages matching the glob pattern.
# regex(.*-\\.beta)   | Matches packages matching re-style regex.
# requirement(foo-5+) | Matches packages within the given requirement.
# before(1429830188)  | Matches packages released before the given date.
# after(1429830188)   | Matches packages released after the given date.
# *.beta              | Same as glob(*.beta)
# foo-5+              | Same as range(foo-5+)
package_filter = None

# If True, unversioned packages are allowed. Solve times are slightly better if
# this value is False.
allow_unversioned_packages = True


###############################################################################
# Environment Resolution
###############################################################################

# Rez's default behaviour is to overwrite variables on first reference. This
# prevents unconfigured software from being used within the resolved environment.
# For example, if PYTHONPATH were to be appended to and not overwritten, then
# python modules from the parent environment would be (incorrectly) accessible
# within the Rez environment.
#
# "Parent variables" override this behaviour - they are appended/prepended to,
# rather than being overwritten. If you set "all_parent_variables" to true, then
# all variables are considered parent variables, and the value of "parent_variables"
# is ignored. Be aware that if you make variables such as PATH, PYTHONPATH or
# app plugin paths parent variables, you are exposing yourself to potentially
# incorrect behaviour within a resolved environment.
parent_variables = []
all_parent_variables = False

# When two or more packages in a resolve attempt to set the same environment
# variable, Rez's default behaviour is to flag this as a conflict and abort the
# resolve. You can overcome this in a package's commands section by using the
# Rex command "resetenv" instead of "setenv". However, you can also turn off this
# behaviour globally - for certain variables, by adding them to "resetting_variables",
# and for all variables, by setting "all_resetting_variables" to true.
resetting_variables = []
all_resetting_variables = False

# The default shell type to use when creating resolved environments (eg when using
# rez-env, or calling ResolvedContext.execute_shell). If empty or null, the
# current shell is used (for eg, "bash").
default_shell = ""

# The command to use to launch a new Rez environment in a separate terminal (this
# is enabled using rez-env's "detached" option). If None, it is detected.
terminal_emulator_command = None

# subprocess.Popen arguments to use in order to execute a shell in a new process
# group (see ResolvedContext.execute_shell, 'start_new_session'). Dict of
# (Popen argument, value).
new_session_popen_args = None

# This setting can be used to override the separator used for environment
# variables that represent a list of items. By default, the value of os.pathsep
# will be used, unless the environment variable is list here, in which case the
# configured separator will be used.
env_var_separators = {
    "CMAKE_MODULE_PATH": ";",
    "DOXYGEN_TAGFILES": " ",
}

# Defines what suites on $PATH stay visible when a new rez environment is resolved.
# Possible values are:
# - "never":            Don"t attempt to keep any suites visible in a new env
# - "always":           Keep suites visible in any new env
# - "parent":           Keep only the parent suite of a tool visible
# - "parent_priority":  Keep all suites visible and the parent takes precedence
suite_visibility = "always"

# Defines how Rez's command line tools are added back to PATH within a resolved
# environment. Valid values are:
# - "append": Rez tools are appended to PATH (default);
# - "prepend": Rez tools are prepended to PATH;
# - "never": Rez tools are not added back to PATH - rez will not be available
#   within resolved shells.
rez_tools_visibility = "append"

# Defines when package commands are sourced during the startup sequence of an
# interactive shell. If True, package commands are sourced before startup
# scripts (such as .bashrc). If False, package commands are sourced after.
package_commands_sourced_first = True

# Defines paths to initially set $PATH to, if a resolve appends/prepends $PATH.
# If this is an empty list, then this initial value is determined automatically
# depending on the shell (for example, *nix shells create a temp clean shell and
# get $PATH from there; Windows inspects its registry).
standard_system_paths = []

# If you define this function, it will be called as the *preprocess function*
# on every package that does not provide its own, as part of the build process.
# The given function must be made available by setting the value of
# [package_definition_build_python_paths](#package_definition_build_python_paths)
# appropriately.
#
# For example, consider the settings:
#
#     package_definition_build_python_paths = ["/src/rezutils"]
#     package_preprocess_function = "build.validate"
#
# This would use the 'validate' function in the sourcefile /src/rezutils/build.py
# to preprocess every package definition file that does not define its own
# preprocess function.
#
# If the preprocess function raises an exception, an error message is printed,
# and the preprocessing is not applied to the package. However, if the
# *InvalidPackageError* exception is raised, the build is aborted.
#
# You would typically use this to perform common validation or modification of
# packages. For example, your common preprocess function might check that the
# package name matches a regex. Here's what that might look like:
#
#     # in /src/rezutils/build.py
#     import re
#     from rez.exceptions import InvalidPackageError
#
#     def validate(package, data):
#         regex = re.compile("(a-zA-Z_)+$")
#         if not regex.match(package.name):
#             raise InvalidPackageError("Invalid package name.")
#
package_preprocess_function = None


###############################################################################
# Tracking
###############################################################################

# Send data to AMQP whenever a context is created or sourced.
# The payload is like so:
#
#     {
#         "action": "created",
#         "host": "some_fqdn",
#         "user": "${USER}",
#         "context": {
#             ...
#         }
#     }
#
# Action is one of ("created", "sourced"). Routing key is set to
# '{exchange_routing_key}.{action|upper}', eg 'REZ.CONTEXT.SOURCED'. "Created"
# is when a new context is constructed, which will either cause a resolve to
# occur, or fetches a resolve from the cache. "Sourced" is when an existing
# context is recreated (eg loading an rxt file).
#
# The "context" field contains the context itself (the same as what is present
# in an rxt file), filtered by the fields listed in 'context_tracking_context_fields'.
#
# Tracking is enabled if 'context_tracking_host' is non-empty. Set to "stdout"
# to just print the message to standard out instead, for testing purposes.
# Otherwise, '{host}[:{port}]' is expected.
#
# If any items are present in 'context_tracking_extra_fields', they are added
# to the payload. If any extra field contains references to unknown env-vars, or
# is set to an empty string (possibly due to var expansion), it is removed from
# the message payload.
#

context_tracking_host = ''

context_tracking_amqp = {
    "userid": '',
    "password": '',
    "connect_timeout": 10,
    "exchange_name": '',
    "exchange_routing_key": 'REZ.CONTEXT',
    "message_delivery_mode": 1
}

context_tracking_context_fields = [
    "status",
    "timestamp",
    "solve_time",
    "load_time",
    "from_cache",
    "package_requests",
    "implicit_packages",
    "resolved_packages"
]

context_tracking_extra_fields = {}


###############################################################################
# Debugging
###############################################################################

# If true, print warnings associated with shell startup sequence, when using
# tools such as rez-env. For example, if the target shell type is "sh", and
# the "rcfile" param is used, you would get a warning, because the sh shell
# does not support rcfile.
warn_shell_startup = False

# If true, print a warning when an untimestamped package is found.
warn_untimestamped = False

# Turn on all warnings
warn_all = False

# Turn off all warnings. This overrides warn_all.
warn_none = False

# Print info whenever a file is loaded from disk, or saved to disk.
debug_file_loads = False

# Print debugging info when loading plugins
debug_plugins = False

# Print debugging info such as VCS commands during package release. Note that
# rez-pip installations are controlled with this setting also.
debug_package_release = False

# Print debugging info in binding modules. Binding modules should print using
# the bind_utils.log() function - it is controlled with this setting
debug_bind_modules = False

# Print debugging info when searching, loading and copying resources.
debug_resources = False

# Print packages that are excluded from the resolve, and the filter rule responsible.
debug_package_exclusions = False

# Print debugging info related to use of memcached during a resolve
debug_resolve_memcache = False

# Debug memcache usage. As well as printing debugging info to stdout, it also
# sends human-readable strings as memcached keys (that you can read by running
# "memcached -vv" as the server)
debug_memcache = False

# Turn on all debugging messages
debug_all = False

# Turn off all debugging messages. This overrides debug_all.
debug_none = False

# When an error is encountered in rex code, rez catches the error and processes
# it, removing internal info (such as the stacktrace inside rez itself) that is
# generally not interesting to the package author. If set to False, rex errors
# are left uncaught, which can be useful for debugging purposes.
catch_rex_errors = True

# Sets the maximum number of characters printed from the stdout / stderr of some
# shell commands when they fail. If 0, then the output is not truncated
shell_error_truncate_cap = 750


###############################################################################
# Build/Release/Copy
###############################################################################

# Whether a package is relocatable or not, if it does not explicitly state with
# the 'relocatable' attribute in its package definition file.
default_relocatable = True

# The default working directory for a package build, relative to the package
# source directory (this is typically where temporary build files are written).
build_directory = "build"

# The number of threads a build system should use, eg the make '-j' option.
# If the string values "logical_cores" or "physical_cores", it is set to the
# detected number of logical / physical cores on the host system.
# (Logical cores are the number of cores reported to the OS, physical are the
# number of actual hardware processor cores.  They may differ if, ie, the CPUs
# support hyperthreading, in which case logical_cores == 2 * physical_cores).
# This setting is exposed as the environment variable $REZ_BUILD_THREAD_COUNT
# during builds.
build_thread_count = "physical_cores"

# The release hooks to run when a release occurs. Release hooks are plugins - if
# a plugin listed here is not present, a warning message is printed. Note that a
# release hook plugin being loaded does not mean it will run - it needs to be
# listed here as well. Several built-in release hooks are available, see
# rezplugins/release_hook.
release_hooks = []

# Prompt for release message using an editor. If set to False, there will be
# no editor prompt.
prompt_release_message = False

# Sometimes a studio will run a post-release process to set a package and its
# payload to read-only. If you set this option to True, processes that mutate an
# existing package (such as releasing a variant into an existing package, or
# copying a package) will, if possible, temporarily make a package writable
# during these processes. The mode will be set back to original afterwards.
#
make_package_temporarily_writable = True

# The subdirectory where hashed variant symlinks (known as variant shortlinks)
# are created. This is only relevant for packages whose 'hashed_variants' is
# set to True. To disable variant shortlinks, set this to None.
#
variant_shortlinks_dirname = "_v"

# Whether or not to use variant shortlinks when resolving variant root paths.
# You might want to disable this for testing purposes, but typically you would
# leave this True.
#
use_variant_shortlinks = True


###############################################################################
# Suites
###############################################################################

# The prefix character used to pass rez-specific commandline arguments to alias
# scripts in a suite. This must be a character other than "-", so that it doesn"t
# clash with the wrapped tools" own commandline arguments.
suite_alias_prefix_char = "+"


###############################################################################
# Appearance
###############################################################################

# Suppress all extraneous output - warnings, debug messages, progress indicators
# and so on. Overrides all warn_xxx and debug_xxx settings.
quiet = False

# Show progress bars where applicable
show_progress = True

# The editor used to get user input in some cases.
# On osx, set this to "open -a <your-app>" if you want to use a specific app.
editor = None

# The program used to view images by tools such as "rez-context -g"
# On osx, set this to "open -a <your-app>" if you want to use a specific app.
image_viewer = None

# The browser used to view documentation; the rez-help tool uses this
# On osx, set this to "open -a <your-app>" if you want to use a specific app.
browser = None

# The viewer used to view file diffs. On osx, set this to "open -a <your-app>"
# if you want to use a specific app.
difftool = None

# The default image format that dot-graphs are rendered to.
dot_image_format = "png"

# If true, tools such as rez-env will update the prompt when moving into a new
# resolved shell. Prompt nerds might do fancy things with their prompt that Rez
# can't deal with (but it can deal with a lot - colors etc - so try it first).
# By setting this to false, Rez will not change the prompt. Instead, you will
# probably want to set it yourself in your startup script (.bashrc etc). You will
# probably want to use the environment variable $REZ_ENV_PROMPT, which contains
# the set of characters that are normally prefixed/suffixed to the prompt, ie
# '>', '>>' etc.
set_prompt = True

# If true, prefixes the prompt, suffixes if false. Ignored if 'set_prompt' is
# false.
prefix_prompt = True


###############################################################################
# Misc
###############################################################################

# If not zero, truncates all package changelog entries to this maximum length.
# You should set this value - changelogs can theoretically be very large, and
# this adversely impacts package load times.
max_package_changelog_chars = 65536

# If not zero, truncates all package changelogs to only show the last N commits
max_package_changelog_revisions = 0

###############################################################################
# Rez-1 Compatibility
###############################################################################

# If this is true, rxt files are written in yaml format. If false, they are
# written in json, which is a LOT faster. You would only set to true for
# backwards compatibility reasons. Note that rez will detect either format on
# rxt file load.
rxt_as_yaml = False

# Warn or disallow when a package is found to contain old rez-1-style commands.
warn_old_commands = True
error_old_commands = False

# Print old commands and their converted rex equivalent. Note that this can
# cause very verbose output.
debug_old_commands = False

# Warn or disallow an extra commands entry called "commands2". This is provided
# as a temporary measure for porting packages to rez-based commands without
# breaking compatibility with Rez-1. If "commands2" is present, it is used
# instead of "commands". Unlike "commands", "commands2" only allows new rex-
# style commands. Once you have fully deprecated Rez-1, you should stop using
# "commands2".
# TODO DEPRECATE
warn_commands2 = False
error_commands2 = False

# If True, Rez will continue to generate the given environment variables in
# resolved environments, even though their use has been deprecated in Rez-2.
# The variables in question, and their Rez-2 equivalent (if any) are:
#
# REZ-1              | REZ-2
# -------------------|-----------------
# REZ_REQUEST        | REZ_USED_REQUEST
# REZ_RESOLVE        | REZ_USED_RESOLVE
# REZ_VERSION        | REZ_USED_VERSION
# REZ_PATH           | REZ_USED
# REZ_RESOLVE_MODE   | not set
# REZ_RAW_REQUEST    | not set
# REZ_IN_REZ_RELEASE | not set
rez_1_environment_variables = True

# If True, Rez will continue to generate the given CMake variables at build and
# release time, even though their use has been deprecated in Rez-2.  The
# variables in question, and their Rez-2 equivalent (if any) are:
#
# REZ-1   | REZ-2
# --------|---------------
# CENTRAL | REZ_BUILD_TYPE
rez_1_cmake_variables = True

# If True, override all compatibility-related settings so that Rez-1 support is
# deprecated. This means that:
# * All warn/error settings in this section of the config will be set to
#   warn=False, error=True;
# * rez_1_environment_variables will be set to False.
# * rez_1_cmake_variables will be set to False.
# You should aim to do this - it will mean your packages are more strictly
# validated, and you can more easily use future versions of Rez.
disable_rez_1_compatibility = False


###############################################################################
# Help
###############################################################################

# Where Rez's own documentation is hosted
documentation_url = " http://nerdvegas.github.io/rez/"


###############################################################################
# Colorization
###############################################################################

# The following settings provide styling information for output to the console,
# and is based on the capabilities of the Colorama module
# (https://pypi.python.org/pypi/colorama).
#
# *_fore and *_back colors are based on the colors supported by this module and
# the console. One or more styles can be applied using the *_styles
# configuration. These settings will also affect the logger used by rez.
#
# At the time of writing, valid values are:
# fore/back: black, red, green, yellow, blue, magenta, cyan, white
# style: dim, normal, bright

# Enables/disables colorization globally.
#
# > [[media/icons/warning.png]] Note: Turned off for Windows currently as there seems
# > to be a problem with the Colorama module.
#
# May also set to the string "force", which will make rez output color styling
# information, even if the the output streams are not ttys. Useful if you are
# piping the output of rez, but will eventually be printing to a tty later.
# When force is used, will generally be set through an environment variable, eg:
#
#     echo $(REZ_COLOR_ENABLED=force python -c "from rez.utils.colorize import Printer, local; Printer()('foo', local)")
color_enabled = (os.name == "posix")

### Do not move or delete this comment (__DOC_END__)

# Logging colors
#------------------------------------------------------------------------------
critical_fore = "red"
critical_back = None
critical_styles = ["bright"]

error_fore = "red"
error_back = None
error_styles = None

warning_fore = "yellow"
warning_back = None
warning_styles = None

info_fore = "green"
info_back = None
info_styles = None

debug_fore = "blue"
debug_back = None
debug_styles = None

# Context-sensitive colors
#------------------------------------------------------------------------------
# Heading
heading_fore = None
heading_back = None
heading_styles = ["bright"]

# Local packages
local_fore = "green"
local_back = None
local_styles = None

# Implicit packages
implicit_fore = "cyan"
implicit_back = None
implicit_styles = None

# Tool aliases in suites
alias_fore = "cyan"
alias_back = None
alias_styles = None


###############################################################################
# Plugin Settings
###############################################################################

# Settings specific to certain plugin implementations can be found in the
# "rezconfig" file accompanying that plugin. The settings listed here are
# common to all plugins of that type.

plugins = {
    "release_vcs": {
        # Format string used to determine the VCS tag name when releasing. This
        # will be formatted using the package being released - any package
        # attribute can be referenced in this string, eg "{name}".
        #
        # It is not recommended to write only '{version}' to the tag. This will
        # cause problems if you ever store multiple packages within a single
        # repository - versions will clash and this will cause several problems.
        "tag_name": "{qualified_name}",

        # A list of branches that a user is allowed to rez-release from. This
        # can be used to block releases from development or feature branches,
        # and support a workflow such as "gitflow".  Each branch name should be
        # a regular expression that can be used with re.match(), for example
        # "^master$".
        "releasable_branches": [],

        # If True, a release will be cancelled if the repository has already been
        # tagged at the current package's version. Generally this is not needed,
        # because Rez won't re-release over the top of an already-released
        # package anyway (or more specifically, an already-released variant).
        #
        # However, it is useful to set this to True when packages are being
        # released in a multi-site scenario. Site A may have released package
        # foo-1.4, and for whatever reason this package hasn't been released at
        # site B. Site B may then make some changes to the foo project, and then
        # attempt to release a foo-1.4 that is now different to site A's foo-1.4.
        # By setting this check to True, this situation can be avoided (assuming
        # that both sites are sharing the same code repository).
        #
        # Bear in mind that even in the above scenario, there are still cases
        # where you may NOT want to check the tag. For example, an automated
        # service may be running that detects when a package is released at
        # site A, which then checks out the code at site B, and performs a
        # release there. In this case we know that the package is already released
        # at A, but that's ok because the package hasn't changed and we just want
        # to release it at B also. For this reason, you can set tag checking to
        # False both in the API and via an option on the rez-release tool.
        "check_tag": False
    }
}



###############################################################################
###############################################################################
# GUI
###############################################################################
###############################################################################

# All of the settings listed here onwards apply only to the GUIs available in
# the "rezgui" part of the module.

# Setting either of these options to true will force rez to select that qt
# binding. If both are false, the qt binding is detected. Setting both to true
# will cause an error.
use_pyside = False
use_pyqt = False

# Turn GUI threading on/off. You would only turn off for debugging purposes.
gui_threads = True


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
