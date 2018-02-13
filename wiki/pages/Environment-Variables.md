This chapter lists the environment variables that rez generates in certain
circumstances, as well as environment variables that you can set which affect
the operation of rez.

## Resolved Environment Variables

These are variables that rez generates within a resolved environment.

* **REZ_RXT_FILE** - Filepath of the current context (an rxt file).
* **REZ_USED** - Path to rez installation that was used to resolve this environment.
* **REZ_USED_IMPLICIT_PACKAGES** - The list of implicit packages used in the resolve.
* **REZ_USED_PACKAGES_PATH** - The package searchpath used for this resolve.
* **REZ_USED_RESOLVE** - The list of resolved packages, eg *"platform-linux utils-1.2.3"*.
* **REZ_USED_REQUEST** - The environment request string, eg *"maya-2017 maya_utils-1.3+"*.
  Does not include implicit packages.
* **REZ_USED_REQUESTED_TIMESTAMP** - The epoch time of this resolved environment,
  explicitly set by the user with (for example) the rez-env '\-\-time' flag; zero otherwise.
* **REZ_USED_TIMESTAMP** - The epoch time when this environment was resolved; OR,
  the value of *REZ_USED_REQUESTED_TIMESTAMP*, if non-zero.
* **REZ_USED_VERSION** - The version of rez used to resolve this environment.

Specifically, per-package, the following variables are generated. Note that for a given
package name, *"(PKG)"* in the variables below is the uppercased package name.

* **REZ_(PKG)_BASE** - The base directory of the package installation, eg
  *"/packages/utils/1.0.0"*.
* **REZ_(PKG)_ROOT** - The root directory of the package installation (actually,
  the variant), eg *"/packages/utils/1.0.0/python-2.7"*.
* **REZ_(PKG)_VERSION** - The version of the package.
* **REZ_(PKG)_MAJOR_VERSION** - The major version of the package, or ''.
* **REZ_(PKG)_MINOR_VERSION** - The minor version of the package, or ''.
* **REZ_(PKG)_PATCH_VERSION** - The patch version of the package, or ''.

## Resolved Build Environment Variables

These are variables that rez generates within a build environment; this is in
addition to those listed [here](#resolved-environment-variables).

* **REZ_BUILD_ENV** - Always present in a build, has value 1.
* **REZ_BUILD_INSTALL** - Has a value of 1 if an installation is taking place
  (either a *rez-build -i* or *rez-release*), otherwise 0.
* **REZ_BUILD_INSTALL_PATH** - Installation path, if an install is taking place.
* **REZ_BUILD_PATH** - Path where build output goes.
* **REZ_BUILD_PROJECT_DESCRIPTION** - Equal to the *description* attribute of the
  package being built.
* **REZ_BUILD_PROJECT_FILE** - The filepath of the package being built (typically
  a *package.py* file).
* **REZ_BUILD_PROJECT_NAME** - Name of the package being built.
* **REZ_BUILD_PROJECT_VERSION** - Version of the package being built.
* **REZ_BUILD_REQUIRES** - The list of requirements for the build - comes from
  the current package's *requires*, *build_requires* and *private_build_requires*
  attributes, including the current variant's requirements.
* **REZ_BUILD_REQUIRES_UNVERSIONED** - Equivalent but unversioned list to
  *REZ_BUILD_REQUIRES*.
* **REZ_BUILD_SOURCE_PATH** - Path containing the package.py file.
* **REZ_BUILD_THREAD_COUNT** - Number of threads being used for the build.
* **REZ_BUILD_TYPE** - One of *local* or *central*. Value is *central* if a
  release is occurring.
* **REZ_BUILD_VARIANT_INDEX** - Zero-based index of the variant currently being built.

## System Environment Variables

These are environment variables that the user can set, which affect the
operation of rez.

* **REZ_(CONFIG_ENTRY)** - For any given rez config entry (see *rezconfig.py*),
  you can override the setting with an environment variable, for convenience. Here,
  *(CONFIG_ENTRY)* is the uppercased equivalent of the setting name. For example,
  a setting commonly overriden this way is *packages_path*, whos equivalent
  variable is *REZ_PACKAGES_PATH*.
* **EDITOR** - On Linux and OSX systems, this will set the default editor to use
  if and when rez requires one (an example is on release if the *prompt_release_message*
  config setting is true).
* **REZ_KEEP_TMPDIRS** - If set to a non-empty string, this prevents rez from
  cleaning up any temporary directories. This is for debugging purposes.
* **REZ_SIGUSR1_ACTION** - If you set this to *print_stack*, rez will prints its
  current stacktrace to stdout if sent a USR1 signal. This is for debugging purposes.
