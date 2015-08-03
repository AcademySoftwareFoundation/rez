"""
Rez configuration settings. Do not change this file.

Settings are determined in the following way:
1) The setting is first read from this file;
2) The setting is then overridden if it is present in another settings file
   pointed at by the $REZ_CONFIG_FILE environment variable;
3) The setting is further overriden if it is present in $HOME/.rezconfig;
4) The setting is overridden again if the environment variable $REZ_XXX is
   present, where XXX is the uppercase version of the setting key. For example,
   "image_viewer" will be overriden by $REZ_IMAGE_VIEWER. List values can be
   separated either with "," or blank space.
5) This is a special case applied only during a package build or release. In
   this case, if the package definition file contains a "config" section,
   settings in this section will override all others.

Note that in the case of plugin settings (anything under the "plugins" section
of the config), (4) does not apply.

Variable expansion can be used in configuration settings. The following
expansions are supported:
- Any property of the system object: Eg "{system.platform}" (see system.py)
- Any environment variable: Eg "${HOME}"

The following variables are provided if you are using rezconfig.py files:
- 'rez_version': The current version of rez.

Paths should use the path separator appropriate for the operating system
(based on Python's os.path.sep).  So for Linux paths, / should be used. On
Windows \ (unescaped) should be used.
"""
import os


###############################################################################
# Paths
###############################################################################

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
# system - for example, *nix distributions will probably set this to "/tmp".
tmpdir = None


###############################################################################
# Extensions
###############################################################################

# Search path for plugins
plugin_path = []

# Search path for bind modules
bind_module_path = []


###############################################################################
# Caching
###############################################################################

# Use available caching mechanisms to speed up resolves when applicable.
resolve_caching = True

# Cache package file reads
cache_package_files = True

# Cache directory traversals
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
variant_select_mode = "version_priority"

# Package filter. One or more filters can be listed, each with a list of
# exclusion and inclusion rules. These filters are applied to each package
# during a resolve, and if any filter excludes a package, that package is not
# included in the resolve. Here is a simple example:
#
# package_filter:
#     excludes:
#     - glob(*.beta)
#     includes:
#     - glob(foo-*)
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
# package_filter:
# - excludes:
#   - glob(*.beta)
# - excludes:
#   - after(1429830188)
#   includes:
#   - foo  # same as range(foo), same as glob(foo-*)
#
# This example shows why multiple filters are supported - with only one filter,
# it would not be possible to exclude all beta packages (including foo), but also
# exclude all packages after a certain date, except for foo.
#
# Following are examples of all the possible rules:
#
# glob(*.beta)          Matches packages matching the glob pattern.
# regex(.*-\\.beta)     Matches packages matching re-style regex.
# requirement(foo-5+)   Matches packages within the given requirement.
# before(1429830188)    Matches packages released before the given date.
# after(1429830188)     Matches packages released after the given date.
# *.beta                Same as glob(*.beta)
# foo-5+                Same as range(foo-5+)
package_filter = None


###############################################################################
# Environment Resolution
###############################################################################

# Rez's default behaviour is to overwrite variables on first reference. This
# prevents unconfigured software from being used within the resolved environment.
# For example, if PYTHONPATH were to be appended to and not overwritten, then
# python modules from the parent environment would be (incorrectly) accessible
# within the Rez environment.
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

# Print info whenever a file is loaded from disk.
debug_file_loads = False

# Print debugging info when loading plugins
debug_plugins = False

# Print debugging info such as VCS commands during package release
debug_package_release = False

# Print debugging info in binding modules. Binding modules should print using
# the bind_utils.log() function - it is controlled with this setting
debug_bind_modules = False

# Print debugging info when searching and loading resources.
debug_resources = False

# Print packages that are excluded from the resolve, and the filter rule responsible.
debug_package_exclusions = False

# Print debugging info related to use of memcached during a resolve
debug_resolve_memcache = False

# Debug memcache usage. This doesn"t spam stdout, instead it sends human-readable
# strings as memcached keys (that you can read by running "memcached -vv" as the
# server).
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


###############################################################################
# Build
###############################################################################

# The default working directory for a package build, relative to the package
# source directory (this is typically where temporary build files are written).
build_directory = "build"


###############################################################################
# Release
###############################################################################

# The release hooks to run when a release occurs. Release hooks are plugins - if
# a plugin listed here is not present, a warning message is printed. Note that a
# release hook plugin being loaded does not mean it will run - it needs to be
# listed here as well. Several built-in release hooks are available, see
# rezplugins/release_hook.
release_hooks = []


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
max_package_changelog_chars = 1024


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
# Note: Turned off for Windows currently as there seems to be a problem with
# the Colorama module.
color_enabled = (os.name == "posix")

#------------------------------------------------------------------------------
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

info_fore = None
info_back = None
info_styles = None

debug_fore = "blue"
debug_back = None
debug_styles = None

#------------------------------------------------------------------------------
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
# Rez-1 Compatibility
###############################################################################

# Warn or disallow when a package contains a package name that does not match
# the name specified in the directory structure. When this occurs, the
# directory package name is used in preference.
warn_package_name_mismatch = True
error_package_name_mismatch = False

# Warn or disallow when a package contains a version number that does not match
# the version specified in the directory structure. When this occurs, the
# directory version number is used in preference.
warn_version_mismatch = True
error_version_mismatch = False

# Warn or disallow when a package is found to contain a non-string version. This
# was possible in Rez-1 but was an oversight - versions could be integer or
# float, as well as string. When this occurs, the directory version number is
# used in preference.
warn_nonstring_version = True
error_nonstring_version = False

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
#   REZ-1               REZ-2
#   -----               -----
#   REZ_REQUEST         REZ_USED_REQUEST
#   REZ_RESOLVE         REZ_USED_RESOLVE
#   REZ_VERSION         REZ_USED_VERSION
#   REZ_PATH            REZ_USED
#   REZ_RESOLVE_MODE    not set
#   REZ_RAW_REQUEST     not set
#   REZ_IN_REZ_RELEASE  not set
rez_1_environment_variables = True

# If True, Rez will continue to generate the given CMake variables at build and
# release time, even though their use has been deprecated in Rez-2.  The
# variables in question, and their Rez-2 equivalent (if any) are:
#   REZ-1               REZ-2
#   -----               -----
#   CENTRAL             REZ_BUILD_TYPE
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
