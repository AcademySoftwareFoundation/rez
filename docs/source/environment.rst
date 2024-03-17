=====================
Environment variables
=====================

This chapter lists the environment variables that rez generates in certain
circumstances, as well as environment variables that you can set which affect
the operation of rez.

.. _context-environment-variables:

Context Environment Variables
=============================

These are variables that rez generates within a resolved environment (a "context").

.. envvar:: REZ_RXT_FILE

   Filepath of the current context (an rxt file).

   .. seealso:: Documentation on :doc:`contexts <context>`.

.. envvar:: REZ_USED

   Path to rez installation that was used to resolve this environment.

.. envvar:: REZ_USED_IMPLICIT_PACKAGES

   The list of implicit packages used in the resolve.

.. envvar:: REZ_USED_PACKAGES_PATH

   The package search-path used for this resolve.

.. envvar:: REZ_USED_RESOLVE

   The list of resolved packages, eg ``platform-linux utils-1.2.3``.

.. envvar:: REZ_USED_EPH_RESOLVE

   The list of resolved ephemerals, eg ``.foo.cli-1 .debugging-0``.

.. envvar:: REZ_USED_LOCAL_RESOLVE

   The list of resolved local packages, eg ``utils-1.2.3 maya_utils-1.3+``. Packages listed here will always be a subset of the packages in :envvar:`REZ_USED_RESOLVE`.

.. envvar:: REZ_USED_REQUEST

   The environment request string, eg ``maya-2017 maya_utils-1.3+``. Does not include implicit packages.

.. envvar:: REZ_USED_REQUESTED_TIMESTAMP

   The epoch time of this resolved environment, explicitly set by the user with (for example) the :option:`rez-env --time` flag; zero otherwise.

.. envvar:: REZ_USED_TIMESTAMP

   The epoch time when this environment was resolved; OR, the value of :envvar:`REZ_USED_REQUESTED_TIMESTAMP`, if non-zero.

.. envvar:: REZ_USED_VERSION

   The version of rez used to resolve this environment.

.. envvar:: REZ_SHELL_INIT_TIMESTAMP

   The epoch time when the current shell was instantiated.

.. envvar:: REZ_SHELL_INTERACTIVE

   Will be 1 if the shell is interactive, and 0 otherwise
   (ie, when a command is specified, like ``rez-env foo -- mycommand``).

.. envvar:: REZ_CONTEXT_FILE

   Filepath of the current context's shell code that is the result of all the
   resolved packages :func:`commands`'s sections.

Package environment variables
-----------------------------

Specifically, per-package, the following variables are generated. Note that for a given
package name, ``(PKG)`` in the variables below is the uppercased package name, with any
dots replaced with underscore.

.. envvar:: REZ_(PKG)_BASE

   The base directory of the package installation, eg ``/packages/utils/1.0.0``.

.. envvar:: REZ_(PKG)_ROOT

   The root directory of the package installation (actually,the variant), eg ``/packages/utils/1.0.0/python-2.7``.

.. envvar:: REZ_(PKG)_VERSION

   The version of the package.

.. envvar:: REZ_(PKG)_MAJOR_VERSION

   The major version of the package, or an empty string.

.. envvar:: REZ_(PKG)_MINOR_VERSION

   The minor version of the package, or an empty string.

.. envvar:: REZ_(PKG)_PATCH_VERSION

   The patch version of the package, or an emopty string.

Ephemeral packages environment variables
----------------------------------------

For every ephemeral package request, the following variables are generated. Note
that for a given ephemeral package name, ``(PKG)`` in the variables below is the
uppercased package name, with dots replaced by underscore, and **the leading dot
removed**:

.. envvar:: REZ_EPH_(PKG)_REQUEST

   The resolved ephemeral package request.

.. _build-environment-variables:

Build Environment Variables
===========================

These are variables that rez generates within a :ref:`build environment <the-build-environment>`, in addition
to context environment variables listed :ref:`here <context-environment-variables>`.

.. glossary::

.. envvar:: REZ_BUILD_ENV

   Always present in a build, has value 1.

.. envvar:: REZ_BUILD_INSTALL

   Has a value of 1 if an installation is taking place (either a :option:`rez-build -i` or :ref:`rez-release`), otherwise 0.

.. envvar:: REZ_BUILD_INSTALL_PATH

   Installation path, if an install is taking place.

.. envvar:: REZ_BUILD_PATH

   Path where build output goes.

.. envvar:: REZ_BUILD_PROJECT_DESCRIPTION

   Equal to the *description* attribute of the  package being built.

.. envvar:: REZ_BUILD_PROJECT_FILE

   The filepath of the package being built (typically a ``package.py`` file).

.. envvar:: REZ_BUILD_PROJECT_NAME

   Name of the package being built.

.. envvar:: REZ_BUILD_PROJECT_VERSION

   Version of the package being built.

.. envvar:: REZ_BUILD_REQUIRES

   Space-separated list of requirements for the build - comes from the current package's :attr:`requires`,
   :attr:`build_requires` and :attr:`private_build_requires` attributes, including the current variant's requirements.

.. envvar:: REZ_BUILD_REQUIRES_UNVERSIONED

   Equivalent but unversioned list to :envvar:`REZ_BUILD_REQUIRES`.

.. envvar:: REZ_BUILD_SOURCE_PATH

   Path containing the package.py file.

.. envvar:: REZ_BUILD_THREAD_COUNT
   :noindex:

   Number of threads being used for the build.

   .. seealso:: The :data:`build_thread_count` setting.

.. envvar:: REZ_BUILD_TYPE

   One of ``local`` or ``central``. Value is ``central`` if a  release is occurring.

.. envvar:: REZ_BUILD_VARIANT_INDEX

   Zero-based index of the variant currently being built. For non-varianted packages, this is 0.

.. envvar:: REZ_BUILD_VARIANT_REQUIRES

   Space-separated list of runtime requirements of the current variant. This does not include
   the common requirements as found in :envvar:`REZ_BUILD_REQUIRES`. For non-varianted builds, this is an empty string.

.. envvar:: REZ_BUILD_VARIANT_SUBPATH

   Subdirectory containing the current variant. For non-varianted builds, this is an empty string.

.. envvar:: __PARSE_ARG_XXX

   .. seealso:: :ref:`custom-build-commands-pass-arguments`

.. _runtime-environment-variables:

Runtime Environment Variables
=============================

These are environment variables that the user can set, which affect the
operation of rez.

.. envvar:: REZ_CONFIG_FILE

   Path to a rez configuration file.

.. envvar:: REZ_XXX

   For any given rez config entry (see ``rezconfig.py``),
   you can override the setting with an environment variable, for convenience. Here,
   ``XXX`` is the uppercased equivalent of the setting name. For example,
   a setting commonly overriden this way is :data:`packages_path`, whos equivalent
   variable is :envvar:`REZ_PACKAGES_PATH`.

   .. hint::
      Each setting documented in :ref:`configuring-rez-configuration-settings` documents their environment variable.

.. envvar:: REZ_XXX_JSON

   Same as :envvar:`REZ_XXX`, except that the format
   is a JSON string. This means that some more complex settings can be overridden,
   that aren't supported in the non-JSON case (:data:`package_filter` is an example).

.. envvar:: REZ_DISABLE_HOME_CONFIG

   If 1/t/true, the default ``~/.rezconfig.py`` config file is skipped.

.. envvar:: EDITOR

   On Linux and OSX systems, this will set the default editor to use
   if and when rez requires one (an example is on release if the :data:`prompt_release_message`
   config setting is true).

.. envvar:: REZ_KEEP_TMPDIRS

   If set to a non-empty string, this prevents rez from
   cleaning up any temporary directories. This is for debugging purposes.

.. envvar:: REZ_ENV_PROMPT

   See the :data:`set_prompt` and :data:`prefix_prompt` settings.

.. envvar:: REZ_LOGGING_CONF

   Path to a file that will be consumed by :func:`logging.config.fileConfig` to configure
   the logger.


Development Environment Variables
=================================

.. envvar:: REZ_LOG_DEPRECATION_WARNINGS

   Enable all deprecation warnings to be logged regardless of how you have configured
   your python interpreter. This is usefull to help upgrading to newer versions of rez.
   Prior to updating, you should set this environment variable to see if you need to
   change some things to be compatible with newer versions.

   .. warning::

      Enabling this will forcefully load every configuration file instead of loading them
      lazilly. This can have an impact on startup time.

.. envvar:: REZ_SIGUSR1_ACTION

   If you set this to ``print_stack``, rez will prints its
   current stacktrace to stdout if sent a USR1 signal. This is for debugging purposes only.

.. envvar:: _REZ_NO_KILLPG

   By default, rez will try to kill its process group when it receives a :data:`SIGINT <signal.SIGINT>`
   or :data:`SIGTERM <signal.SIGTERM>` signal. Setting ``_REZ_NO_KILLPG`` to either "1", "true", "on"
   or "yes" disables this behavior. This is handy when developing rez itself.

.. envvar:: _REZ_QUIET_ON_SIG

   Print a message if rez receives a :data:`SIGINT <signal.SIGINT>`
   or :data:`SIGTERM <signal.SIGTERM>` signal.
