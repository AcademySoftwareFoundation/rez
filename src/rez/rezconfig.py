# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Rez configuration settings. Do not change this file.

Settings are determined in the following way (higher number means higher
precedence):

1) The setting is first read from this file;
2) The setting is then overridden if it is present in another settings file(s)
   pointed at by the $REZ_CONFIG_FILE environment variable. Note that multiple
   files are supported, separated by os.pathsep;
3) The setting is further overriden if it is present in $HOME/.rezconfig,
  UNLESS $REZ_DISABLE_HOME_CONFIG is 1;
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
Windows \\ (unescaped! A change in python 3.12 does not allow single backslashes
in docstrings. Sorry.) should be used.

Note: The comments in this file are extracted and turned into documentation. Pay
attention to the comment formatting and follow the existing style closely.
"""

# flake8: noqa

import os

### Do not move or delete this comment (__DOC_START__)

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

# The path that Rez will locally install packages to when :ref:`rez-build` is used
local_packages_path = "~/packages"

# The path that Rez will deploy packages to when :ref:`rez-release` is used. For
# production use, you will probably want to change this to a site-wide location.
release_packages_path = "~/.rez/packages/int"

# Where temporary files go. Defaults to appropriate path depending on your
# system. For example, \*nix distributions will probably set this to :file:`/tmp`. It
# is highly recommended that this be set to local storage, such as :file:`/tmp`.
tmpdir = None

# Where temporary files for contexts go. Defaults to appropriate path depending
# on your system. For example, \*nix distributions will probably set this to :file:`/tmp`.
# This is separate to :data:`tmpdir` because you sometimes might want to set this to an
# NFS location. For example, perhaps rez is used during a render and you'd like
# to store these tempfiles in the farm queuer's designated tempdir so they're
# cleaned up when the render completes.
context_tmpdir = None

# These are extra python paths that are added to :data:`sys.path` **only during a build**.
# This means that any of the functions in the following list can import modules
# from these paths:
#
# * The :func:`preprocess` function;
# * Any function decorated with :ref:`@early <package-definition-early-binding-functions>`. These get evaluated at build time.
#
# You can use this to provide common code to your package definition files during
# a build. To provide common code for packages to use at resolve time instead (for
# example, in a :func:`commands` function) see the following
# :data:`package_definition_python_path` setting.
package_definition_build_python_paths = []

# This is the directory from which installed packages can import modules. This
# is a way for packages to use shared code.
#
# This is NOT a standard path added to :data:`sys.path`. Packages that use modules from
# within this directory need to explicitly name them. Furthermore, modules that
# a package uses are copied into that package's install. This ensures that the
# package remains standalone and that changes to the shared code will not break
# or alter existing package installs.
#
# Consider the setting:
#
# .. code-block:: python
#
#    package_definition_python_path = "/src/rezutils"
#
# Consider also the following package :func:`commands` function:
#
# .. code-block:: python
#
#    @include("utils")
#    def commands():
#        utils.do_some_common_thing(this)
#
# This package will import the code from :file:`/src/rezutils/utils.py` (or more
# specifically, its copy of this sourcefile) and will bind it to the name ``utils``.
#
# For further information, see :ref:`package-definition-sharing-code`.
package_definition_python_path = None


###############################################################################
# Extensions
###############################################################################

# Search path for rez plugins.
plugin_path = []

# Search path for bind modules. The :ref:`rez-bind` tool uses these modules to create
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
# example, the URI ``127.0.0.1:11211`` points to memcached running on localhost on
# its default port. Must be either None, or a list of strings.
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
# Package Copy
###############################################################################

# Whether a package is relocatable or not, if it does not explicitly state with
# the :attr:`relocatable` attribute in its package definition file.
default_relocatable = True

# Set relocatable on a per-package basis. This is here for migration purposes.
# It's better for packages themselves to set their relocatable attribute.
# Overrides :data:`default_relocatable` if a package matches.
#
# Example:
#
# .. code-block:: python
#
#    default_relocatable_per_package = {
#        "nuke": False,
#        "maya": True
#    }
default_relocatable_per_package = None

# Set relocatable on a per-package-repository basis. Overrides
# :data:`default_relocatable_per_package` and :data:`default_relocatable` for any repos
# listed here.
#
# Example:
#
# .. code-block:: python
#
#    default_relocatable_per_repostitory = {
#        '/svr/packages': False
#    }
default_relocatable_per_repository = None


###############################################################################
# Package Caching
#
# Package caching refers to copying variant payloads to a path on local
# disk, and using those payloads instead. It is a way to avoid fetching files
# over shared storage, and is unrelated to memcached-based caching of resolves
# and package definitions as seen in the "Caching" config section.
#
###############################################################################

# Whether a package is cachable or not, if it does not explicitly state with
# the :attr:`cachable` attribute in its package definition file. If None, defaults
# to packages' relocatability (ie cachable == relocatable).
default_cachable = False

# Set cachable on a per-package basis. This is here for migration purposes.
# It's better for packages themselves to set their cachable attribute. Overrides
# :data:`default_cachable` if a package matches.
#
# Example:
#
# .. code-block:: python
#
#    default_cachable_per_package = {
#        "nuke": False,
#        "maya": True
#    }
default_cachable_per_package = None

# Set cachable on a per-package-repository basis. Overrides
# :data:`default_cachable_per_package` and :data:`default_cachable` for any repos listed here.
#
# Example:
#
# .. code-block:: python
#
#    default_cachable_per_repostitory = {
#        '/svr/packages': False
#    }
default_cachable_per_repository = None

# The path where rez locally caches variants. If this is None, then package
# caching is disabled.
cache_packages_path = None

# If True, variants in a resolve will use locally cached payloads if they are
# present in the cache.
read_package_cache = True

# If True, creating or sourcing a context will cause variants to be cached.
write_package_cache = True

# Delete variants that haven't been used in N days (see :option:`rez-pkg-cache --clean`).
# To disable, set to zero.
package_cache_max_variant_days = 30

# Enable package caching during a package build.
package_cache_during_build = False

# Asynchronously cache packages. If this is false, resolves will block until
# all packages are cached.
#
# .. versionadded:: 3.2.0
package_cache_async = True

# Allow caching of local packages. You would only want to set this True for
# testing purposes.
package_cache_local = False

# Allow package caching if the source package is on the same physical disk
# as the package cache itself. You would only want to set this True for testing
# purposes.
package_cache_same_device = False

# If > 0, spend up to this many seconds cleaning the cache every time the cache
# is updated. This is a way to keep the cache size under control without having
# to periodically run :option:`rez-pkg-cache --clean`. Set to -1 to disable.
package_cache_clean_limit = 0.5

# Number of days of package cache logs to keep.
# Logs are written to :file:`{pkg-cache-root}/.sys/log/{filename}.log`
package_cache_log_days = 7


###############################################################################
# Package Resolution
###############################################################################

# Packages that are implicitly added to all package resolves, unless the
# :option:`rez-env --no-implicit` flag is used.
implicit_packages = [
    "~platform=={system.platform}",
    "~arch=={system.arch}",
    "~os=={system.os}",
]

# Override platform values from Platform.os and arch.
# This is useful as Platform.os might show different
# values depending on the availability of ``lsb-release`` on the system.
# The map supports regular expression, e.g. to keep versions.
#
# .. note::
#    The following examples are not necessarily recommendations.
#
# .. code-block:: python
#
#    platform_map = {
#        "os": {
#            r"Scientific Linux-(.*)": r"Scientific-\1",                 # Scientific Linux-x.x -> Scientific-x.x
#            r"Ubuntu-14.\d": r"Ubuntu-14",                              # Any Ubuntu-14.x      -> Ubuntu-14
#            r'CentOS Linux-(\d+)\.(\d+)(\.(\d+))?': r'CentOS-\1.\2', '  # Centos Linux-X.Y.Z -> CentOS-X.Y
#        },
#        "arch": {
#            "x86_64": "64bit",                                          # Maps both x86_64 and amd64 -> 64bit
#            "amd64": "64bit",
#        },
#    }
platform_map = {}

# If true, then when a resolve graph is generated during a failed solve, packages
# unrelated to the failure are pruned from the graph. An "unrelated" package is
# one that is not a dependency ancestor of any packages directly involved in the
# failure.
prune_failed_graph = True

# Variant select mode. This determines which variants in a package are preferred
# during a solve. Valid options are:
#
# - **version_priority**: Prefer variants that contain higher versions of packages
#   present in the request;
# - **intersection_priority**: Prefer variants that contain the most number of
#   packages that are present in the request.
#
# As an example, suppose you have a package foo which has two variants:
#
# .. code-block:: python
#
#    variants = [
#        ["bar-3.0", "baz-2.1"],
#        ["bar-2.8", "burgle-1.0"]
#    ]
#
# if you do ``rez-env foo bar`` then, in either variant_select_mode,
# it will prefer the first variant, ``["bar-3.0", "baz-2.1"]``, because it has a
# higher version of the first variant requirement (bar). However, if we instead do
# ``rez-env foo bar burgle`` we get different behavior. version_priority mode will
# still return ``["bar-3.0", "baz-2.1"]``, because the first requirement's version is higher.
#
# However, ``intersection_priority`` mode will pick the second variant,
# ``["bar-2.8", "burgle-1.0"]``, because it contains more packages that were in the
# original request (burgle).
variant_select_mode = "version_priority"

# One or more filters can be listed, each with a list of
# exclusion and inclusion rules. These filters are applied to each package
# during a resolve, and if any filter excludes a package, that package is not
# included in the resolve. Here is a simple example:
#
# .. code-block:: python
#
#    package_filter = {
#        'excludes': 'glob(*.beta)',
#        'includes': 'glob(foo-*)',
#    }
#
# This is an example of a single filter with one exclusion rule and one inclusion
# rule. The filter will ignore all packages with versions ending in ``.beta``,
# except for package ``foo`` (which it will accept all versions of). A filter will
# only exclude a package if that package matches at least one exclusion rule,
# and does not match any inclusion rule.
#
# Here is another example, which excludes all beta and dev packages, and all
# packages except ``foo`` that are released after a certain date. Note that in
# order to use multiple filters, you need to supply a list of dicts, rather
# than just a dict:
#
# .. code-block:: python
#
#    package_filter = [
#        {
#            'excludes': ['glob(*.beta)', 'glob(*.dev)']
#        },
#        {
#            'excludes': ['after(1429830188)'],
#            'includes': ['foo'],  # same as range(foo), same as glob(foo-*)
#        }
#    ]
#
# This example shows why multiple filters are supported. With only one filter,
# it would not be possible to exclude all beta and dev packages (including foo),
# but also exclude all packages after a certain date, except for foo.
#
# Following are examples of all the possible rules:
#
# ======================== ====================================================
# Example                  Description
# ======================== ====================================================
# ``glob(*.beta)``         Matches packages matching the glob pattern.
# ``regex(.*-\\.beta)``    Matches packages matching re-style regex.
# ``range(foo-5+)``        Matches packages within the given requirement.
# ``before(1429830188)``   Matches packages released before the given date.
# ``after(1429830188)``    Matches packages released after the given date.
# ``*.beta``               Same as glob(\*.beta).
# ``foo-5+``               Same as range(foo-5+).
# ======================== ====================================================
package_filter = None

# One or more "orderers" can be listed.
# This will affect the order of version resolution.
# This can be used to ensure that specific version have priority over others.
# Higher versions can still be accessed if explicitly requested.
package_orderers = None

# If True, unversioned packages are allowed. Solve times are slightly better if
# this value is False.
allow_unversioned_packages = True

# Defines whether a resolve should immediately fail if any variants have a required package that can't be found.
# This can be useful to disable if you have packages that aren't available to all users.
# It is enabled by default. If a variant has requires that cannot be found , it will error immediately rather than
# trying the other variants.
# If disabled, it will try other variants before giving up.
#
# .. warning::
#    Memcached isn't tested with scenarios where you expect users to have access to different sets of packages.
#    It expects that every user can access the same set of packages, which may cause incorrect resolves
#    when this option is disabled.
error_on_missing_variant_requires = True

###############################################################################
# Environment Resolution
###############################################################################

# Rez's default behaviour is to overwrite variables on first reference. This
# prevents unconfigured software from being used within the resolved environment.
# For example, if PYTHONPATH were to be appended to and not overwritten, then
# python modules from the parent environment would be (incorrectly) accessible
# within the Rez environment.
#
# "Parent variables" override this behaviour. They are appended/prepended to,
# rather than being overwritten. If you set :data:`all_parent_variables` to :data:`True`, then
# all variables are considered parent variables, and the value of :data:`parent_variables`
# is ignored. Be aware that if you make variables such as ``PATH``, :envvar:`PYTHONPATH` or
# app plugin paths parent variables, you are exposing yourself to potentially
# incorrect behaviour within a resolved environment.
parent_variables = []

# See :data:`parent_variables`.
all_parent_variables = False

# When two or more packages in a resolve attempt to set the same environment
# variable, Rez's default behaviour is to flag this as a conflict and abort the
# resolve. You can overcome this in a package's commands section by using the
# Rex command :func:`resetenv` instead of :func:`setenv`. However, you can also turn off this
# behaviour globally for some varibles by adding them to :data:`resetting_variables`,
# and for all variables, by setting :data:`all_resetting_variables` to true.
resetting_variables = []

# See :data:`resetting_variables`.
all_resetting_variables = False

# The default shell type to use when creating resolved environments (eg when using
# :ref:`rez-env`, or calling :meth:`.ResolvedContext.execute_shell`). If empty or None, the
# current shell is used (for eg, "bash").
#
# .. versionchanged:: 3.0.0
#    The default value on Windows was changed to "powershell".
default_shell = ""

# The command to use to launch a new Rez environment in a separate terminal (this
# is enabled using the :option:`rez-env --detached` option). If None, it is detected.
terminal_emulator_command = None

# :class:`subprocess.Popen` arguments to use in order to execute a shell in a new process
# group (see :meth:`.ResolvedContext.execute_shell` and its ``start_new_session`` argument).
# Dict of (Popen argument, value).
new_session_popen_args = None

# This setting can be used to override the separator used for environment
# variables that represent a list of items. By default, the value of :data:`os.pathsep`
# will be used, unless the environment variable is list here, in which case the
# configured separator will be used.
env_var_separators = {
    "CMAKE_MODULE_PATH": ";",
    "DOXYGEN_TAGFILES": " ",
}

# This setting identifies path-like environment variables. This is required
# because some shells need to apply path normalization. For example, the command
# ``env.PATH.append("{root}/bin")`` will be normalized to (eg) ``C:\...\bin`` in a
# ``cmd`` shell on Windows. Note that wildcards are supported. If this setting is
# not correctly configured, then your shell may not work correctly.
pathed_env_vars = [
    "*PATH"
]

# Defines what suites on ``$PATH`` stay visible when a new rez environment is resolved.
# Possible values are:
#
# - "never":            Don"t attempt to keep any suites visible in a new env
# - "always":           Keep suites visible in any new env
# - "parent":           Keep only the parent suite of a tool visible
# - "parent_priority":  Keep all suites visible and the parent takes precedence
suite_visibility = "always"

# Defines how Rez's command line tools are added back to ``$PATH`` within a resolved
# environment. Valid values are:
#
# - "append": Rez tools are appended to PATH (default);
# - "prepend": Rez tools are prepended to PATH;
# - "never": Rez tools are not added back to PATH. Rez will not be available
#   within resolved shells.
rez_tools_visibility = "append"

# Defines when package commands are sourced during the startup sequence of an
# interactive shell. If True, package commands are sourced before startup
# scripts (such as ``.bashrc``). If False, package commands are sourced after.
package_commands_sourced_first = True

# Defines paths to initially set ``$PATH`` to, if a resolve appends/prepends ``$PATH``.
# If this is an empty list, then this initial value is determined automatically
# depending on the shell (for example, \*nix shells create a temp clean shell and
# get ``$PATH`` from there; Windows inspects its registry).
standard_system_paths = []

# If you define this function, by default it will be called as the
# *preprocess function* on every package that does not provide its own,
# as part of the build process. This behavior can be changed by using the
# :data:`package_preprocess_mode` setting so that
# it gets executed even if a package define its own preprocess function.
#
# The setting can be a function defined in your ``rezconfig.py``, or a string.
#
# Example of a function to define the setting:
#
# .. code-block:: python
#
#    # in your rezconfig.py
#    def package_preprocess_function(this, data):
#        # some custom code...
#
# In the case where the function is a string, it must be made available by setting
# the value of :data:`package_definition_build_python_paths` appropriately.
#
# For example, consider the settings:
#
# .. code-block:: python
#
#    package_definition_build_python_paths = ["/src/rezutils"]
#    package_preprocess_function = "build.validate"
#
# This would use the ``validate`` function in the sourcefile :file:`/src/rezutils/build.py`
# to preprocess every package definition file that does not define its own
# preprocess function.
#
# If the preprocess function raises an exception, an error message is printed,
# and the preprocessing is not applied to the package. However, if the
# :exc:`~rez.exceptions.InvalidPackageError` exception is raised, the build is aborted.
#
# You would typically use this to perform common validation or modification of
# packages. For example, your common preprocess function might check that the
# package name matches a regex. Here's what that might look like:
#
# .. code-block:: python
#
#    # in /src/rezutils/build.py
#    import re
#    from rez.exceptions import InvalidPackageError
#
#    def validate(package, data):
#        regex = re.compile("(a-zA-Z_)+$")
#        if not regex.match(package.name):
#            raise InvalidPackageError("Invalid package name.")
#
package_preprocess_function = None

# Defines in which order the :data:`package_preprocess_function`
# and the :attr:`preprocess` function inside a ``package.py`` are executed.
#
# Note that "global preprocess" means the preprocess defined by
# :data:`package_preprocess_function`.
#
# Possible values are:
#
# - "before": Package's preprocess function is executed before the global preprocess;
# - "after": Package's preprocess function is executed after the global preprocess;
# - "override": Package's preprocess function completely overrides the global preprocess.
package_preprocess_mode = "override"

###############################################################################
# Context Tracking
###############################################################################

# Send data to AMQP server whenever a context is created or sourced.
# The payload is like so:
#
# .. code-block:: python
#
#    {
#        "action": "created",
#        "host": "some_fqdn",
#        "user": "${USER}",
#        "context": {
#            ...
#        }
#    }
#
# Action is one of (``created``, ``sourced``). Routing key is set to
# ``{exchange_routing_key}.{action|upper}``, eg ``REZ.CONTEXT.SOURCED``. ``created``
# is when a new context is constructed, which will either cause a resolve to
# occur, or fetches a resolve from the cache. ``sourced`` is when an existing
# context is recreated (eg loading an rxt file).
#
# The ``context`` field contains the context itself (the same as what is present
# in an rxt file), filtered by the fields listed in :data:`context_tracking_context_fields`.
#
# Tracking is enabled if :data:`context_tracking_host` is non-empty. Set to ``stdout``
# to just print the message to standard out instead, for testing purposes.
# Otherwise, ``{host}[:{port}]`` is expected.
#
# If any items are present in :data:`context_tracking_extra_fields`, they are added
# to the payload. If any extra field contains references to unknown env-vars, or
# is set to an empty string (possibly due to var expansion), it is removed from
# the message payload.
context_tracking_host = ''

# See :data:`context_tracking_host`
context_tracking_amqp = {
    "userid": '',
    "password": '',
    "connect_timeout": 10,
    "exchange_name": '',
    "exchange_routing_key": 'REZ.CONTEXT',
    "message_delivery_mode": 1
}

# See :data:`context_tracking_host`
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

# See :data:`context_tracking_host`
context_tracking_extra_fields = {}


###############################################################################
# Debugging
###############################################################################

# If true, print warnings associated with shell startup sequence, when using
# tools such as :ref:`rez-env`. For example, if the target shell type is ``sh``, and
# the ``rcfile`` param is used, you would get a warning, because the sh shell
# does not support rcfile.
warn_shell_startup = False

# If true, print a warning when an untimestamped package is found.
warn_untimestamped = False

# Turn on all warnings
warn_all = False

# Turn off all warnings. This overrides :data:`warn_all`.
warn_none = False

# Print info whenever a file is loaded from disk, or saved to disk.
debug_file_loads = False

# Print debugging info when loading plugins
debug_plugins = False

# Print debugging info such as VCS commands during package release. Note that
# :ref:`rez-pip` installations are controlled with this setting also.
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
# ``memcached -vv`` as the server)
debug_memcache = False

# Print debugging info when an AMPQ server is used in context tracking
debug_context_tracking = False

# Turn on all debugging messages
debug_all = False

# Turn off all debugging messages. This overrides :data:`debug_all`.
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
# Package Build/Release
###############################################################################

# The default working directory for a package build, either absolute path or
# relative to the package source directory (this is typically where temporary
# build files are written).
build_directory = "build"

# The number of threads a build system should use, eg the make ``-j`` option.
# If the string values ``logical_cores`` or ``physical_cores`` are used, it is set to the
# detected number of logical / physical cores on the host system.
# (Logical cores are the number of cores reported to the OS, physical are the
# number of actual hardware processor cores. They may differ if, ie, the CPUs
# support hyperthreading, in which case ``logical_cores == 2 * physical_cores``).
# This setting is exposed as the environment variable :envvar:`REZ_BUILD_THREAD_COUNT`
# during builds.
build_thread_count = "physical_cores"

# The release hooks to run when a release occurs. Release hooks are plugins. If
# a plugin listed here is not present, a warning message is printed. Note that a
# release hook plugin being loaded does not mean it will run. It needs to be
# listed here as well. Several built-in release hooks are available, see
# :gh-rez:`src/rezplugins/release_hook`.
release_hooks = []

# Prompt for release message using an editor. If set to False, there will be
# no editor prompt.
prompt_release_message = False

# Sometimes a studio will run a post-release process to set a package and its
# payload to read-only. If you set this option to True, processes that mutate an
# existing package (such as releasing a variant into an existing package, or
# copying a package) will, if possible, temporarily make a package writable
# during these processes. The mode will be set back to original afterwards.
make_package_temporarily_writable = True

# The subdirectory where hashed variant symlinks (known as variant shortlinks)
# are created. This is only relevant for packages whose 'hashed_variants' is
# set to True. To disable variant shortlinks, set this to None.
variant_shortlinks_dirname = "_v"

# Whether or not to use variant shortlinks when resolving variant root paths.
# You might want to disable this for testing purposes, but typically you would
# leave this True.
use_variant_shortlinks = True

# Default build process to use during build/release.
# Only 'local' build process is currently available,
# see :gh-rez:`src/rezplugins/build_process`.
#
# .. versionadded:: 3.2.0
default_build_process = "local"


###############################################################################
# Suites
###############################################################################

# The prefix character used to pass rez-specific command line arguments to alias
# scripts in a suite. This must be a character other than ``-``, so that it doesn"t
# clash with the wrapped tools" own commandline arguments.
suite_alias_prefix_char = "+"


###############################################################################
# Appearance
###############################################################################

# Suppress all extraneous output (warnings, debug messages, progress indicators
# and so on). Overrides all ``warn_xxx`` and ``debug_xxx settings``.
quiet = False

# Show progress bars where applicable
show_progress = True

# The editor used to get user input in some cases.
# On macOS, set this to ``open -a <your-app>`` if you want to use a specific app.
editor = None

# The program used to view images by tools such as :option:`rez-context -g`
# On macOS, set this to ``open -a <your-app>`` if you want to use a specific app.
image_viewer = None

# The browser used to view documentation. The :ref:`rez-help` tool uses this
# On macOS, set this to ``open -a <your-app>`` if you want to use a specific app.
browser = None

# The viewer used to view file diffs. On macOS, set this to ``open -a <your-app>``
# if you want to use a specific app.
difftool = None

# The default image format that dot-graphs are rendered to.
dot_image_format = "png"

# If true, tools such as :ref:`rez-env` will update the prompt when moving into a new
# resolved shell. Prompt nerds might do fancy things with their prompt that Rez
# can't deal with (but it can deal with a lot (colors etc) so try it first).
# By setting this to False, Rez will not change the prompt. Instead, you will
# probably want to set it yourself in your startup script (``.bashrc`` etc). You will
# probably want to use the environment variable :envvar:`REZ_ENV_PROMPT`, which contains
# the set of characters that are normally prefixed/suffixed to the prompt, ie
# ``>``, ``>>`` etc.
set_prompt = True

# If true, prefixes the prompt, suffixes if false. Ignored if :data:`set_prompt` is
# false.
prefix_prompt = True


###############################################################################
# Misc
###############################################################################

# If not zero, truncates all package changelog entries to this maximum length.
# You should set this value. Changelogs can theoretically be very large, and
# this adversely impacts package load times.
max_package_changelog_chars = 65536

# If not zero, truncates all package changelogs to only show the last N commits
max_package_changelog_revisions = 0

# Default option on how to create scripts with :func:`~rez.utils.execution.create_executable_script`.
# In order to support both windows and other OS it is recommended to set this
# to ``both``.
#
# Possible modes:
#
# - single:
#       Creates the requested script only.
# - py:
#       Create ``.py`` script that will allow launching scripts on windows,
#       if the shell adds .py to ``PATHEXT``. Make sure to use :pep:`397` ``py.exe``
#       as default application for ``.py`` files.
# - platform_specific:
#       Will create py script on windows and requested on other platforms
# - both:
#       Creates the requested file and a ``.py`` script so that scripts can be
#       launched without extension from windows and other systems.
create_executable_script_mode = "single"

# Configurable pip extra arguments passed to the :ref:`rez-pip` install command.
# Since the :ref:`rez-pip` install command already includes some pre-configured
# arguments (``--target``, ``--use-pep517``) this setting can potentially override the
# default configuration in a way which can cause package installation issues.
# It is recommended to refrain from overriding the default arguments and only
# use this setting for additional arguments that might be needed.
# https://pip.pypa.io/en/stable/reference/pip_install/#options
pip_extra_args = []

# Substitutions for :func:`re.sub` when unknown parent paths are encountered in the
# pip package distribution record: :file:`{name}.dist-info/RECORD`
#
# Rez reads the distribution record to figure out where pip installed files
# to, then copies them to their final sub-path in the rez package. Ie, python
# source files are hard coded to be moved under the ``python`` sub-folder inside
# the rez package, which then gets added to :envvar:`PYTHONPATH` upon :ref:`rez-env`.
#
# When it can't find the file listed in the record AND the path starts
# with a reference to the parent directory ``..``, the following remaps are
# used to:
#
# 1. Match a path listed in the record to perform the filepath remapping;
# 2. :func:`re.sub` expression from step 1 to make the relative path of where pip
#    actually installed the file to;
# 3. :func:`re.sub` expression from step 1 to make the destination filepath, relative
#    to the rez variant root.
#
# Use these tokens to avoid regular expression and OS-specific path issues:
#
# - "{pardir}" or "{p}" for parent directory: :data:`os.pardir`, i.e. ``..`` on Linux/Mac
# - "{sep}" or "{s}" for folder separators: :data:`os.sep`, i.e. ``/`` on Linux/Mac
pip_install_remaps = [
    # Typical bin copy behaviour
    # Path in record          | pip installed to    | copy to rez destination
    # ------------------------|---------------------|--------------------------
    # ../../bin/*             | bin/*               | bin/*
    {
        "record_path": r"^{p}{s}{p}{s}(bin{s}.*)",
        "pip_install": r"\1",
        "rez_install": r"\1",
    },
    # Fix for #821
    # Path in record          | pip installed to    | copy to rez destination
    # ------------------------|---------------------|--------------------------
    # ../../lib/python/*      | *                   | python/*
    {
        "record_path": r"^{p}{s}{p}{s}lib{s}python{s}(.*)",
        "pip_install": r"\1",
        "rez_install": r"python{s}\1",
    },
]

# A dict type config for storing arbitrary data that can be
# accessed by the :func:`optionvars` function in packages
# :func:`commands`.
#
# This is like user preferences for packages, which may not easy to define in
# package's definition file directly due to the differences between machines/users/pipeline-roles.
#
# Example:
#
# .. code-block:: python
#
#    # in your rezconfig.py
#    optionvars = {
#        "userRoles": ["artist"]
#    }
#
# And to access:
#
# .. code-block:: python
#
#    # in package.py
#    def commands():
#        roles = optionvars("userRoles", default=None) or []
#        if "artist" in roles:
#            env.SOMETHING_FRIENDLY = "Yes"
#
# Note that you can refer to values in nested dicts using dot notation:
#
# .. code-block:: python
#
#    def commands():
#        if optionvars("nuke.lighting_tools_enabled"):
#            ...
optionvars = None

###############################################################################
# Rez-1 Compatibility
#
# These settings are for rez v1 compatibility purposes.
#
###############################################################################

# Warn or disallow when a package is found to contain old rez-1-style commands.
#
# .. deprecated:: 2.114.0
#    Will be removed in a future release.
warn_old_commands = True

# See :data:`warn_old_commands`.
#
# .. deprecated:: 2.114.0
#    Will be removed in a future release.
error_old_commands = False

# Print old commands and their converted rex equivalent. Note that this can
# cause very verbose output.
#
# This currently has no effect.
#
# .. deprecated:: 2.114.0
#    Will be removed in a future version.
debug_old_commands = False

# If True, Rez will continue to generate the given environment variables in
# resolved environments, even though their use has been deprecated in Rez-2.
# The variables in question, and their Rez-2 equivalent (if any) are:
#
# .. deprecated:: 2.114.0
#    Will be removed in a future release.
#
# .. versionchanged:: 3.0.0
#    Changed the default value to False in preparation of future removal.
#
# ================== ==========================
# REZ-1              REZ-2
# ================== ==========================
# REZ_REQUEST        :envvar:`REZ_USED_REQUEST`
# REZ_RESOLVE        :envvar:`REZ_USED_RESOLVE`
# REZ_VERSION        :envvar:`REZ_USED_VERSION`
# REZ_PATH           :envvar:`REZ_USED`
# REZ_RESOLVE_MODE   not set
# REZ_RAW_REQUEST    not set
# REZ_IN_REZ_RELEASE not set
# ================== ==========================
rez_1_environment_variables = False

# If True, override all compatibility-related settings so that Rez-1 support is
# deprecated. This means that:
#
# * All warn/error settings in this section of the config will be set to
#   warn=False, error=True;
# * :data:`rez_1_environment_variables` will be set to False.
#
# You should aim to do this. It will mean your packages are more strictly
# validated, and you can more easily use future versions of Rez.
#
# .. deprecated:: 2.114.0
#    Will be removed in a future release.
#
# .. versionchanged:: 3.0.0
#    Changed the default value to True in preparation of future removal.
#
disable_rez_1_compatibility = True


###############################################################################
# Help
###############################################################################

# Where Rez's own documentation is hosted
documentation_url = "https://rez.readthedocs.io"


###############################################################################
# Colorization
#
# The following settings provide styling information for output to the console,
# and is based on the capabilities of the Colorama module
# (https://pypi.python.org/pypi/colorama).
#
# \*_fore and \*_back colors are based on the colors supported by this module and
# the console. One or more styles can be applied using the \*_styles
# configuration. These settings will also affect the logger used by rez.
#
# At the time of writing, valid values are:
# fore/back: black, red, green, yellow, blue, magenta, cyan, white
# style: dim, normal, bright
#
###############################################################################

# Enables/disables colorization globally.
#
# .. warning::
#    Turned off for Windows currently as there seems to be a problem with the colorama module.
#
# May also set to the string ``force``, which will make rez output color styling
# information, even if the the output streams are not ttys. Useful if you are
# piping the output of rez, but will eventually be printing to a ``tty`` later.
# When force is used, will generally be set through an environment variable, eg:
#
# .. code-block:: text
#
#    echo $(REZ_COLOR_ENABLED=force python -c "from rez.utils.colorize import Printer, local; Printer()('foo', local)")
#
# TODO: Colorama is documented to work on Windows and trivial test case
# proves this to be the case, but it doesn't work in Rez (with cmd.exe).
# If the initialise is called in src/rez/__init__.py then it does work,
# however this is not always desirable.
# As it does with with some Windows shells it can be enabled in rezconfig
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

# Ephemerals
ephemeral_fore = "blue"
ephemeral_back = None
ephemeral_styles = None

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
