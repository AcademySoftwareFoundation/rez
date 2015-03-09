#------------------------------------------------------------------------------
# Rez configuration settings. Do not change this file.
#
# Settings are determined in the following way:
# 1) The setting is first read from this file;
# 2) The setting is then overridden if it is present in another settings file
#    pointed at by the $REZ_CONFIG_FILE environment variable;
# 3) The setting is further overriden if it is present in $HOME/.rezconfig;
# 4) The setting is overridden again if the environment variable $REZ_XXX is
#    present, where XXX is the uppercase version of the setting key. For example,
#    'image_viewer' will be overriden by $REZ_IMAGE_VIEWER. List values can be
#    separated either with ',' or blank space.
# 5) This is a special case applied only during a package build or release. In
#    this case, if the package definition file contains a 'config' section,
#    settings in this section will override all others.
#
# Note that in the case of plugin settings (anything under the 'plugins'
# section of the config), (4) does not apply.
#
# Variable expansion can be used in configuration settings. The following
# expansions are supported:
# - Any property of the system object: Eg '{system.platform}' (see system.py)
# - Any environment variable: Eg '${HOME}'
#
# Paths should use the path separator appropriate for the operating system
# (based on Python's os.path.sep).  So for Linux paths, / should be used.  On
# Windows \ (unescaped) should be used.
#------------------------------------------------------------------------------

import os

###############################################################################
# Paths
###############################################################################

# The package search path. Rez uses this to find packages. A package with the
# same name and version in an earlier path takes precedence.
if os.name == "posix":
    packages_path = [
        '~/packages'           # locally installed pkgs, not yet deployed
        '~/.rez/packages/int'  # internally developed pkgs, deployed
        '~/.rez/packages/ext'  # external (3rd party) pkgs, such as houdini, boost
    ]

else:
    packages_path = [
        '~\packages'           # locally installed pkgs, not yet deployed
        '~/.rez\packages\int'  # internally developed pkgs, deployed
        '~\.rez\packages\ext'  # external (3rd party) pkgs, such as houdini, boost
    ]

# The path that Rez will locally install packages to when rez-build is used
if os.name == "posix":
    local_packages_path = '~/packages'

else:
    local_packages_path = '~\packages'

# The path that Rez will deploy packages to when rez-release is used. For
# production use, you will probably want to change this to a site-wide location.
if os.name == "posix":
    release_packages_path = '~/.rez/packages/int'

else:
    release_packages_path = '~\.rez\packages\int'

# Where temporary files go. Defaults to appropriate path depending on your
# system, for example linux distributions will probably set this to /tmp.
tmpdir = None


###############################################################################
# Extensions
###############################################################################

# Search path for plugins
plugin_path = []

# Search path for bind modules
bind_module_path = []


###############################################################################
# Resources
###############################################################################

# If True, enable resource caching. This caches things such as disk reads of
# package.yaml files, and data validation. You would only turn this off for
# debugging purposes.
resource_caching = True

# The size of the resource cache. This is measured in the number of items in the
# cache where each might be a resource, directory listing, of resource path
# parser regular expression: these all contribute to the resource cache.
# A value of 0 has the same effect as setting resource_caching to false.  A
# value of -1 creates a cache of unlimited size.  Any other value introduces an
# lru cache fixed at that size.
resource_caching_maxsize = -1


###############################################################################
# Package Resolution
###############################################################################

# Packages that are implicitly added to all package resolves, unless the
# --no-implicit flag is used.
implicit_packages = [
    '~platform=={system.platform}',
    '~arch=={system.arch}',
    '~os=={system.os}',
]

# Use available caching mechanisms to speed up resolves when applicable.
resolve_caching = True

# 'start_depth' and 'max_depth' are used to delay loading older packages until
# necessary. More recent packages are searched first, and then if a solution is
# not found, older packages may be searched in subsequent solves.
#
# This often results in faster solves, because generally speaking, older packages
# are used less often. If 'start_depth' is specified, multiple solves are performed,
# with the depth doubling until either all relevant packages are being loaded, or
# a solution is found. Some examples of possible scenarios are:
#
# max_depth  start_depth  effect
# ---------  -----------  ------
# 0          0            All packages are loaded; one solve is performed.
# N          0            Only the latest N packages are loaded; one solve is
#                         performed.
# 0          N            Multiple solves are performed, with the search depth N
#                         doubling with each solve.
# M          N            Multiple solves are performed, with the search depth N
#                         doubling with each solve. The depth is truncated at M.
#
# Note that depth settings still work when resolving with a timestamp - the
# latest N packages *at that time* will be used in the search.
#
resolve_start_depth = 1
resolve_max_depth = 0

# If true, then when a resolve graph is generated during a failed solve, packages
# unrelated to the failure are pruned from the graph. An 'unrelated' package is
# one that is not a dependency ancestor of any packages directly involved in the
# failure.
prune_failed_graph = True

###############################################################################
# Environment Resolution
###############################################################################

# Rez's default behaviour is to overwrite variables on first reference. This
# prevents unconfigured software from being used within the resolved environment.
# For example, if PYTHONPATH were to be appended to and not overwritten, then
# python modules from the parent environment would be (incorrectly) accessible
# within the Rez environment.
# 'Parent variables' override this behaviour - they are appended/prepended to,
# rather than being overwritten. If you set 'all_parent_variables' to true, then
# all variables are considered parent variables, and the value of 'parent_variables'
# is ignored. Be aware that if you make variables such as PATH, PYTHONPATH or
# app plugin paths parent variables, you are exposing yourself to potentially
# incorrect behaviour within a resolved environment.
parent_variables = []
all_parent_variables = False

# When two or more packages in a resolve attempt to set the same environment
# variable, Rez's default behaviour is to flag this as a conflict and abort the
# resolve. You can overcome this in a package's commands section by using the
# Rex command 'resetenv' instead of 'setenv'. However, you can also turn off this
# behaviour globally - for certain variables, by adding them to 'resetting_variables',
# and for all variables, by setting 'all_resetting_variables' to true.
resetting_variables = []
all_resetting_variables = False

# The default shell type to use when creating resolved environments (eg when using
# rez-env, or calling ResolvedContext.execute_shell). If empty or null, the
# current shell is used (for eg, 'bash').
default_shell = ''

# The command to use to launch a new Rez environment in a separate terminal (this
# is enabled using rez-env's 'detached' option). If None, it is detected.
terminal_emulator_command = None

# This setting can be used to override the separator used for environment
# variables that represent a list of items. By default, the value of os.pathsep
# will be used, unless the environment variable is list here, in which case the
# configured separator will be used.
env_var_separators = {
    'CMAKE_MODULE_PATH': ';',
}


###############################################################################
# Debugging
###############################################################################

# If true, print warnings associated with shell startup sequence, when using
# tools such as rez-env. For example, if the target shell type is 'sh', and
# the 'rcfile' param is used, you would get a warning, because the sh shell
# does not support rcfile.
warn_shell_startup = False

# If true, print a warning when an untimestamped package is found.
warn_untimestamped = False

# Turn on all warnings
warn_all = False

# Turn off all warnings. This overrides warn_all.
warn_none = False

# Print debugging info when loading plugins
debug_plugins = False

# Print debugging info such as VCS commands during package release
debug_package_release = False

# Print debugging info in binding modules. Binding modules should print using
# the bind_utils.log() function - it is controlled with this setting
debug_bind_modules = False

# Print debugging info when searching and loading resources.
debug_resources = False

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
build_directory = 'build'


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
# scripts in a suite. This must be a character other than '-', so that it doesn't
# clash with the wrapped tools' own commandline arguments.
suite_alias_prefix_char = '+'


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

# The program used to view images by tools such as 'rez-context -g'
# On osx, set this to "open -a <your-app>" if you want to use a specific app.
image_viewer = None

# The browser used to view documentation; the rez-help tool uses this
# On osx, set this to "open -a <your-app>" if you want to use a specific app.
browser = None

# The default image format that dot-graphs are rendered to.
dot_image_format = 'png'

# If true, prefixes the prompt, suffixes if false
prefix_prompt = True


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
if os.name == "posix":
    color_enabled = True

else:
    color_enabled = False

#------------------------------------------------------------------------------
# Logging colors
#------------------------------------------------------------------------------
critical_fore = 'red'
critical_back = None
critical_styles = [
    'bright',
]

error_fore = 'red'
error_back = None
error_styles = None

warning_fore = 'yellow'
warning_back = None
warning_styles = None

info_fore = None
info_back = None
info_styles = None

debug_fore = 'blue'
debug_back = None
debug_styles = None

#------------------------------------------------------------------------------
# Context-sensitive colors
#------------------------------------------------------------------------------
# Heading
heading_fore = None
heading_back = None
heading_styles = [
    'bright',
]

# Local packages
local_fore = 'green'
local_back = None
local_styles = None

# Implicit packages
implicit_fore = 'cyan'
implicit_back = None
implicit_styles = None

# Tool aliases in suites
alias_fore = 'cyan'
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

# Warn or disallow an extra commands entry called 'commands2'. This is provided
# as a temporary measure for porting packages to rez-based commands without
# breaking compatibility with Rez-1. If 'commands2' is present, it is used
# instead of 'commands'. Unlike 'commands', 'commands2' only allows new rex-
# style commands. Once you have fully deprecated Rez-1, you should stop using
# 'commands2'.
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
documentation_url = 'http://nerdvegas.github.io/rez/'


###############################################################################
# Plugin Settings
###############################################################################

# Settings specific to certain plugin implementations can be found in the
# 'rezconfig' file accompanying that plugin. The settings listed here are
# common to all plugins of that type.

plugins = {
    'release_vcs': {
        # Format string used to determine the VCS tag name when releasing. This
        # will be formatted using the package being released - any package
        # attribute can be referenced in this string, eg '{name}'.
        'tag_name': '{qualified_name}',

        # A list of branches that a user is allowed to rez-release from. This
        # can be used to block releases from development or feature branches,
        # and support a workflow such as 'gitflow'.  Each branch name should be
        # a regular expression that can be used with re.match(), for example
        # '^master$'.
        'releasable_branches': [
        ]
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
