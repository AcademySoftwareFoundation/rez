================
Package commands
================

Package definition files (``package.py``) usually define a :func:`.commands` section. This is a python
function that determines how the environment is configured in order to include the package.

Consider the simple example:

.. code-block:: python

   def commands():
     env.PYTHONPATH.append("{root}/python")
     env.PATH.append("{root}/bin")

This is a typical case, where a package adds its source path to ``PYTHONPATH``, and its tools to
``PATH``. The ``{root}`` string expands to the installation directory of the package.

When a rez environment is configured, every package in the resolve list has its :func:`.commands` section
interpreted and converted into shell code (the language, bash or other, depends on the platform
and is extensible). The resulting shell code is sourced, and this configures the environment.
Within a configured environment, the variable :envvar:`REZ_CONTEXT_FILE` points at this shell code, and the
command :option:`rez-context --interpret` prints it.

The python API that you use in the :func:`.commands` section is called ``rex`` (**R**\ez **EX**\ecution language). It
is an API for performing shell operations in a shell-agnostic way. Some common operations you would
perform with this API include setting environment variables, and appending/prepending path-like
environment variables.

.. note::
   By default, environment variables that are not referenced by any package
   are left unaltered. There will typically be many system variables that are left unchanged.

.. warning:: 
   If you need to import any python modules to use in a :func:`.commands`
   section, the import statements **must** be done inside that function.

.. _package-commands-order-of-execution:

Order Of Command Execution
==========================

The order in which package commands are interpreted depends on two factors: the order in which
the packages were requested, and dependencies between packages. This order can be defined as:

* If package ``A`` was requested before package ``B``, then ``A``'s commands are interpreted before ``B``'s;
* Unless package ``A`` requires (depends on) ``B``, in which case ``B`` will be interpreted before ``A``.

Consider a package ``maya_anim_tool``. Let us say this is a maya plugin. Naturally it has a dependency
on ``maya``, therefore ``maya``'s commands will be interpreted first. This is because the maya plugin
may depend on certain environment variables that ``maya`` sets. For example, ``maya`` might initialize
the ``MAYA_PLUG_IN_PATH`` environment variable, and ``maya_anim_tool`` may then append to this
variable.

For example, consider the request:

.. code-block:: text

   ]$ rez-env maya_anim_tool-1.3+ PyYAML-3.10 maya-2015

Assuming that ``PyYAML`` depends on ``python``, and ``maya_anim_tool`` depends on ``maya``, then the
resulting :func:`.commands` execution order would be:

* maya;
* maya_anim_tool;
* python;
* PyYAML.

.. _variable-appending-and-prepending:

Variable Appending And Prepending
=================================

Path-like environment variables can be appended and prepended like so:

.. code-block:: python

   env.PATH.append("{root}/bin")

However, the first append/prepend operation on any given variable actually **overwrites** the
variable, rather than appending. Why does this happen? Consider ``PYTHONPATH``: if an initial
overwrite did not happen, then any modules visible on ``PYTHONPATH`` before the rez environment was
configured would still be there. This would mean you may not have a properly configured
environment. If your system ``PyQt`` were on ``PYTHONPATH`` for example, and you used :ref:`rez-env` to set
a different ``PyQt`` version, an attempt to import it within the configured environment would still,
incorrectly, import the system version.

.. note::
   ``PATH`` is a special case. It is not simply overwritten, because if that
   happened you would lose important system paths and thus utilities like ``ls`` and ``cd``. In this
   case the system paths are appended back to ``PATH`` after all commands are interpreted. The system
   paths are defined as the default value of ``PATH`` in a non-interactive shell.

.. todo:: Add custom class for "construction"?

.. admonition:: Noteasd

   Better control over environment variable initialization is
   coming. Specifically, you will be able to specify various modes for variables. For example, one
   mode will append the original (pre-rez) value back to the resulting value.

.. _string-expansion:

String Expansion
================

Object Expansion
----------------

Any of the objects available to you in a :func:`commands` section can be referred to in formatted strings
that are passed to rex functions such as :func:`setenv` and so on. For example, consider the code:

.. code-block:: python

   appendenv("PATH", "{root}/bin")

Here, ``{root}`` will expand out to the value of :attr:`root`, which is the installation path of the
package (:attr:`this.root` could also have been used).

You don't *have* to use this feature. It is provided as a convenience. For example, the following
code is equivalent to the previous example, and is just as valid (but more verbose):

.. code-block:: python

   import os.path
   appendenv("PATH", os.path.join(root, "bin"))

Object string expansion is also supported when setting an environment variable via the :attr:`env` object:

.. code-block:: python

   env.FOO_LIC = "{this.root}/lic"

Environment Variable Expansion
------------------------------

Environment variable expansion is also supported when passed to rex functions. Both syntax ``$FOO``
and ``${FOO}`` are supported, regardless of the syntax supported by the target shell.

Literal Strings
---------------

You can use the :func:`literal` function to inhibit object and environment variable string
expansion. For example, the following code will set the environment variable to the literal string:

.. code-block:: python

   env.TEST = literal("this {root} will not expand")

There is also an :func:`expandable` function, which matches the default behavior. You wouldn't typically
use this function. However, you can define a string containing literal and expandable parts by
chaining together :func:`literal` and :func:`expandable`:

.. code-block:: python

   env.DESC = literal("the value of {root} is").expandable("{root}")

.. _explicit-string-expansion:

Explicit String Expansion
-------------------------

Object string expansion usually occurs **only** when a string is passed to a rex function, or to
the :attr:`env` object. For example the simple statement ``var = "{root}/bin"`` would not expand ``{root}``
into ``var``. However, you can use the :func:`expandvars` function to enable this behavior
explicitly:

.. code-block:: python

   var = expandvars("{root}/bin")

The :func:`expandvars` and :func:`expandable` functions are slightly different. :func:`expandable` will generate a
shell variable assignment that will expand out while :func:`expandvars` will expand the value immediately.

This table illustrates the difference between :func:`literal`, :func:`expandable` and :func:`expandvars`:

=================================== =======================
Package command                     Equivalent bash command
=================================== =======================
``env.FOO = literal("${USER}")``    ``export FOO='${USER}'``
``env.FOO = expandable("${USER}")`` ``export FOO="${USER}"``
``env.FOO = expandvars("${USER}")`` ``export FOO="jbloggs"``
=================================== =======================

.. admonition:: Additional context
   :class: admonition note

   In Bash, single quote strings (``'foo'``) will not be expanded.

Filepaths
=========

Rez expects POSIX-style filepath syntax in package commands, regardless of the shell or platform.
Thus, even if you're on Windows, you should do this:

.. code-block:: python

   def commands():
      env.PATH.append("{root}/bin")  # note the forward slash

Where necessary, filepaths will be automatically normalized for you. That is, converted into
the syntax expected by the shell. In order for this to work correctly however, rez needs to know
what environment variables are actually paths. You determine this with the
:data:`pathed_env_vars` config setting. By default, any environment
variable ending in ``PATH`` will be treated as a filepath or list of filepaths, and any
set/append/prepend operation on it will cause those values to be path-normalized automatically.

.. warning::
   Avoid using :data:`os.pathsep` or hardcoded lists of paths such as
   ``{root}/foo:{root}/bah``. Doing so can cause your package to be incompatible with some shells or
   platforms. Even the seemingly innocuous :data:`os.pathsep` is an issue, because there are some cases
   (eg Git for Windows, aka git-bash) where the shell's path separator does not match the underlying
   system's.

Pre And Post Commands
=====================

Occasionally, it's useful for a package to run commands either before or after all other packages,
regardless of the command execution order rules. This can be achieved by defining a :func:`pre_commands`
or :func:`post_commands` function. A package can have any, all or none of :func:`pre_commands`, :func:`commands` and
:func:`post_commands` defined, although it is very common for a package to define just :func:`commands`.

The order of command execution is:

* All package :func:`pre_commands` are executed, in standard execution order;
* Then, all package :func:`commands` are executed, in standard execution order;
* Then, all package :func:`post_commands` are executed, in standard execution order.

.. _pre-build-commands:

Pre Build Commands
==================

If a package is being built, that package's commands are not run, simply because that package is
not present in its own build environment! However, sometimes there is a need to run commands
specifically for the package being built. For example, you may wish to set some environment
variables to pass information along to the build system.

The :func:`pre_build_commands` function does just this. It is called prior to the build. Note that info
about the current build (such as the installation path) is available in a
:attr:`build` object (other commands functions do not have this object visible).

.. _pre-test-commands:

Pre Test Commands
=================

Sometimes it's useful to perform some extra configuration in the environment that a package's test
will run in. You can define the :func:`pre_test_commands` function to do this. It will be invoked just
before the test is run. As well as the standard :attr:`this` object, a :attr:`test` object is also
provided to distinguish which test is about to run.

A Largish Example
=================

Here is an example of a package definition with a fairly lengthy :func:`commands` section:

.. code-block:: python

   name = "foo"

   version = "1.0.0"

   requires = [
      "python-2.7",
      "~maya-2015"
   ]

   def commands():
      import os.path  # imports MUST be inline to the function

      # add python module, executables
      env.PYTHONPATH.append("{this.root}/python")
      env.PATH.append("{this.root}/bin")

      # show include path if a build is occurring
      if building:
         env.FOO_INCLUDE_PATH = "{this.root}/include"

      # debug support to point at local config
      if defined("DEBUG_FOO"):
         conf_file = os.path.expanduser("~/.foo/config")
      else:
         conf_file = "{this.root}/config"
      env.FOO_CONFIG_FILE = conf_file

      # if maya is in use then include the maya plugin part of this package
      if "maya" in resolve:
         env.MAYA_PLUG_IN_PATH.append("{this.root}/maya/plugins")

         if resolve.maya.version.minor == "sp3":
               error("known issue with GL renderer in service pack 3, beware")

      # license file per major version
      env.FOO_LIC = "/lic/foo_{this.version.major}.lic"

Objects
=======

Various objects and functions are available to use in the :func:`commands` function (as well as
:func:`pre_commands` and :func:`post_commands`).

Following is a list of the objects and functions available.

.. .. currentmodule:: pkgdefrex

.. py:function:: alias()

   Create a command alias.

   .. code-block:: python

      alias("nukex", "Nuke -x")

   .. note::
      In ``bash``, aliases are implemented as bash functions.

.. py:attribute:: base
   :type: str

   See :attr:`this.base`.

.. py:attribute:: build

   This is a dict like object. Each key can also be accessed as attributes.

   This object is only available in the :func:`pre_build_commands`
   function. It has the following fields:

   .. code-block:: python

      if build.install:
         info("An installation is taking place")

      if build['build_type'] == 'local':
         pass

.. py:attribute:: build.build_type
   :type: typing.Literal['local', 'central']

   One of ``local``, ``central``. The type is ``central`` if a package release is occurring, and ``local``
   otherwise.

.. py:attribute:: build.install
   :type: bool

   True if an installation is taking place, False otherwise.

.. py:attribute:: build.build_path
   :type: str

   Path to the build directory (not the installation path). This will typically reside somewhere
   within the ``./build`` subdirectory of the package being built.

.. py:attribute:: build.install_path
   :type: str

   Installation directory. Note that this will be set, even if an installation is **not** taking place.

   .. warning::
      Do not check this variable to detect if an installation is occurring. Use :attr:`build.install` instead.

.. py:attribute:: building
   :type: bool

   This boolean variable is ``True`` if a build is occurring (typically done via the :ref:`rez-build` tool),
   and ``False`` otherwise.
   
   However, the :func:`commands` block is only executed when the package is brought
   into a resolved environment, so this is not used when the package itself is building. Typically a
   package will use this variable to set environment variables that are only useful during when other
   packages are being built. C++ header include paths are a good example.

   .. code-block:: python

      if building:
         env.FOO_INCLUDE_PATH = "{root}/include"

.. py:function:: command(arg: str)

   Run an arbitrary shell command.

   Example:

   .. code-block:: python

      command("rm -rf ~/.foo_plugin")

   .. note::
      Note that you cannot return a value from this function call, because
      *the command has not yet run*. All of the packages in a resolve only have their commands executed
      after all packages have been interpreted and converted to the target shell language. Therefore any
      value returned from the command, or any side effect the command has, is not visible to any package.

   You should prefer to perform simple operations (such as file manipulations and so on) in python
   where possible instead. Not only does that take effect immediately, but it's also more cross
   platform. For example, instead of running the command above, we could have done this:

   .. code-block:: python

      def commands():
         import shutil
         import os.path
         path = os.path.expanduser("~/.foo_plugin")
         if os.path.exists(path):
               shutil.rmtree(path)

.. py:function:: comment(arg: str)

   Creates a comment line in the converted shell script code. This is only visible if the user views
   the current shell's code using the command :option:`rez-context --interpret` or looks at the file
   referenced by the environment variable :envvar:`REZ_CONTEXT_FILE`. You would create a comment for debugging
   purposes.

   .. code-block:: python

      if "nuke" in resolve:
         comment("note: taking over 'nuke' binary!")
         alias("nuke", "foo_nuke_replacer")


.. py:function:: defined(envvar: str) -> bool

   Use this boolean function to determine whether or not an environment variable is set.

   .. code-block:: python

      if defined("REZ_MAYA_VERSION"):
         env.FOO_MAYA = 1

.. py:attribute:: env
   :type: dict

   The ``env`` object represents the environment dict of the configured environment. Environment variables
   can also be accessed as attributes.
   
   .. note::
      Note that this is different from the standard python :data:`os.environ` dict, which represents the current environment,
      not the one being configured. If a prior package's :func:`commands` sets a variable via the ``env`` object,
      it will be visible only via ``env``, not :data:`os.environ`. The :data:`os.environ` dict hasn't been updated because the target
      configured environment does not yet exist!

   .. code-block:: python

      env.FOO_DEBUG = 1
      env["BAH_LICENSE"] = "/lic/bah.lic"

.. py:function:: env.append(value: str)

   Appends a value to an environment variable. By default this will use the :data:`os.pathsep` delimiter
   between list items, but this can be overridden using the config setting :data:`env_var_separators`. See
   :ref:`variable-appending-and-prepending` for further information on the behavior of this function.

   .. code-block:: python

      env.PATH.append("{root}/bin")

.. py:function:: env.prepend(value: str)

   Like :func:`env.append`, but prepends the environment variable instead.

   .. code-block:: python

      env.PYTHONPATH.prepend("{root}/python")

.. py:attribute:: ephemerals

   A dict like object representing the list of ephemerals in the resolved environment. Each item is a
   string (the full request, eg ``.foo.cli-1``), keyed by the ephemeral package name. Note
   that you do **not** include the leading ``.`` when getting items from the ``ephemerals``
   object.

   Example:

   .. code-block:: python

      if "foo.cli" in ephemerals:
         info("Foo cli option is being specified!")

.. py:function:: ephemerals.get_range(name: str, range_: str) -> ~rez.version.VersionRange

   Use ``get_range`` to test with the :func:`intersects` function.
   Here, we enable ``foo``'s commandline tools by default, unless explicitly disabled via
   a request for ``.foo.cli-0``:

   .. code-block:: python

      if intersects(ephemerals.get_range("foo.cli", "1"), "1"):
         info("Enabling foo cli tools")
         env.PATH.append("{root}/bin")

.. py:function:: error(message: str)

   Prints to standard error.

   .. note::
      This function just prints the error, it does not prevent the target
      environment from being constructed (use the :func:`stop`) command for that).

   .. code-block:: python

      if "PyQt" in resolve:
         error("The floob package has problems running in combo with PyQt")

.. py:function:: expandable(arg: str) -> ~rez.rex.EscapedString

   See :ref:`explicit-string-expansion`.

.. py:function:: expandvars(arg: str)

   See :ref:`explicit-string-expansion`.

.. py:function:: getenv(envvar: str)

   Gets the value of an environment variable.

   .. code-block:: python

      if getenv("REZ_MAYA_VERSION") == "2016.sp1":
         pass

   :raises RexUndefinedVariableError: if the environment variable is not set.

.. py:attribute:: implicits

   A dict like object that is similar to the :attr:`request` object, but it contains only the package request as
   defined by the :data:`implicit_packages` configuration setting.

   .. code-block:: python

      if "platform" in implicits:
         pass

.. py:function:: info(message: str)

   Prints to standard out.

   .. code-block:: python

      info("floob version is %s" % resolve.floob.version)

.. py:function:: intersects(range1: str | ~rez.version.VersionRange | ~rez.rex_bindings.VariantBinding | ~rez.rex_bindings.VersionBinding, range2: str) -> bool

   A boolean function that returns True if the version or version range of the given
   object, intersects with the given version range. Valid objects to query include:

   * A resolved package, eg ``resolve.maya``;
   * A package request, eg ``request.foo``;
   * A version of a resolved package, eg ``resolve.maya.version``;
   * A resolved ephemeral, eg ``ephemerals.foo``;
   * A version range object, eg ``ephemerals.get_range('foo.cli', '1')``

   .. warning::
      Do **not** do this:

      .. code-block:: python

         if intersects(ephemerals.get("foo.cli", "0"), "1"):
            ...

      .. todo:: document request.get_range

      If ``foo.cli`` is not present, this will unexpectedly compare the unversioned
      package named ``0`` against the version range ``1``, which will succeed! Use
      :func:`ephemerals.get_range` and ``request.get_range`` functions instead:

      .. code-block:: python

         if intersects(ephemerals.get_range("foo.cli", "0"), "1"):
            ...

   Example:

   .. code-block:: python

      if intersects(resolve.maya, "2019+"):
         info("Maya 2019 or greater is present")

.. py:function:: literal(arg: str) -> ~rez.rex.EscapedString

   Inhibits expansion of object and environment variable references.

   .. code-block:: python

      env.FOO = literal("this {root} will not expand")

   You can also chain together ``literal`` and :func:`expandable` functions like so:

   .. code-block:: python

      env.FOO = literal("the value of {root} is").expandable("{root}")

.. py:function:: optionvars(name: str, default: typing.Any | None = None) -> typing.Any

   A :meth:`dict.get` like function for package accessing arbitrary data from :data:`optionvars` in rez config.

.. py:attribute:: request
   :type: ~rez.rex_bindings.RequirementsBinding

   A dict like object representing the list of package requests. Each item is a request string keyed by the
   package name. For example, consider the package request:

   .. code-block:: text

      ]$ rez-env maya-2015 maya_utils-1.2+<2 !corelib-1.4.4

   This request would yield the following ``request`` object:

   .. code-block:: python

      {
         "maya": "maya-2015",
         "maya_utils": "maya_utils-1.2+<2",
         "corelib": "!corelib-1.4.4"
      }

   Use ``get_range`` to test with the :func:`intersects` function:

      if intersects(request.get_range("maya", "0"), "2019"):
         info("maya 2019.* was asked for!")

   Example:

   .. code-block:: python

      if "maya" in request:
         info("maya was asked for!")

   .. tip::
      If multiple requests are present that refer to the same package, the
      request is combined ahead of time. In other words, if requests ``foo-4+`` and ``foo-<6`` were both
      present, the single request ``foo-4+<6`` would be present in the ``request`` object.

.. py:function:: resetenv(envvar: str, value: str, friends=None) -> None

   TODO: Document

.. py:attribute:: resolve

   A dict like object representing the list of packages in the resolved environment. Each item is a
   :ref:`Package <package-attributes>` object, keyed by the package name.

   Packages can be accessed using attributes (ie ``resolve.maya``).

   .. code-block:: python

      if "maya" in resolve:
         info("Maya version is %s", resolve.maya.version)
         # ..or resolve["maya"].version

.. py:attribute:: root
   :type: str

   See :attr:`this.root`.

.. py:function:: setenv(envvar: str, value: str)

   This function sets an environment variable to the given value. It is equivalent to setting a
   variable via the :attr:`env` object (eg, ``env.FOO = 'BAH'``).

   .. code-block:: python

      setenv("FOO_PLUGIN_PATH", "{root}/plugins")

.. py:function:: source(path: str) -> None

   Source a shell script. Note that, similarly to :func:`commands`, this function cannot return a value, and
   any side effects that the script sourcing has is not visible to any packages. For example, if the
   ``init.sh`` script below contained ``export FOO=BAH``, a subsequent test for this variable on the
   :attr:`env` object would yield nothing.

   .. code-block:: python

      source("{root}/scripts/init.sh")

.. py:attribute:: stop(message: str) -> typing.NoReturn

   Raises an exception and stops a resolve from completing. You should use this when an unrecoverable
   error is detected and it is not possible to configure a valid environment.

   .. code-block:: python

      stop("The value should be %s", expected_value)

.. py:attribute:: system
   :type: ~rez.system.System

   This object provided system information, such as current platform, arch and os.

   .. code-block:: python

      if system.platform == "windows":
         ...

.. py:attribute:: test

   Dict like object to access test related attributes. Only available in the :func:`pre_test_commands` function.
   Keys can be accessed as object attributes.

.. py:attribute:: test.name
   :type: str

   Name of the test about to run.

   .. code-block:: python

      if test.name == "unit":
         info("My unit test is about to run yay")

.. py:attribute:: testing
   :type: bool

   This boolean variable is ``True`` if a test is occurring (typically done via the :ref:`rez-test` tool),
   and ``False`` otherwise.
   
   A package can use this variable to set environment variables that are only relevant during test execution.

   .. code-block:: python

      if testing:
          env.FOO_TEST_DATA_PATH = "{root}/tests/data"

.. py:attribute:: this

   The ``this`` object represents the current package. The following attributes are most commonly used
   in a :func:`commands`) section (though you have access to all package attributes. See :ref:`here <package-attributes>`):

   .. py:attribute:: this.base
      :type: str

      Similar to :attr:`this.root`, but does not include the variant subpath, if there is one. Different
      variants of the same package share the same :attr:`base` directory. See :doc:`here <variants>` for more
      information on package structure in relation to variants.

   .. py:attribute:: this.is_package
      :type: bool

      .. todo:: Document

      TODO: Document

   .. py:attribute:: this.is_variant
      :type: bool

      .. todo:: Document 

      TODO: Document

   .. py:attribute:: this.name
      :type: str

      The name of the package, eg ``houdini``.

   .. py:attribute:: this.root
      :type: str

      The installation directory of the package. If the package contains variants, this path will include
      the variant subpath. This is the directory that contains the installed package payload. See
      :doc:`here <variants>` for more information on package structure in relation to variants.

   .. py:attribute:: this.version
      :type: ~rez.rex_bindings.VersionBinding

      The package version. It can be used as a string, however you can also access specific tokens in the
      version (such as major version number and so on), as this code snippet demonstrates:

      .. code-block:: python

         env.FOO_MAJOR = this.version.major  # or, this.version[0]

      The available token references are ``this.version.major``, ``this.version.minor`` and
      ``this.version.patch``, but you can also use a standard list index to reference any version token.

.. py:function:: undefined(envvar: str) -> bool

   Use this boolean function to determine whether or not an environment variable is set. This is the
   opposite of :func:`defined`.

   .. code-block:: python

      if undefined("REZ_MAYA_VERSION"):
         info("maya is not present")

.. py:function:: unsetenv(envvar: str) -> None

   Unsets an environment variable. This function does nothing if the environment variable was not set.

   .. code-block:: python

      unsetenv("FOO_LIC_SERVER")

.. py:attribute:: version
   :type: ~rez.rex_bindings.VersionBinding

   See :attr:`this.version`.
