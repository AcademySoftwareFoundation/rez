## Overview

Package definition files (*package.py*) usually define a *commands* section. This is a python
function that determines how the environment is configured in order to include the package.

Consider the simple example:

    def commands():
      env.PYTHONPATH.append("{root}/python")
      env.PATH.append("{root}/bin")

This is a typical case, where a package adds its source path to PYTHONPATH, and its tools to
PATH. The "{root}" string expands to the installation directory of the package.

When a rez environment is configured, every package in the resolve list has its *commands* section
interpreted and converted into shell code (the language - bash or other - depends on the platform
and is extensible). The resulting shell code is sourced, and this configures the environment.
Within a configured environment, the variable *REZ_CONTEXT_FILE* points at this shell code, and the
command *rez-context --interpet* prints it.

The python API that you use in the *commands* section is called *rex* (Rez EXecution language). It
is an API for performing shell operations in a shell-agnostic way. Some common operations you would
perform with this API include setting environment variables, and appending/prepending path-like
environment variables.

> [[media/icons/info.png]] By default, environment variables that are not referenced by any package
> are left unaltered. There will typically be many system variables that are left unchanged.

> [[media/icons/warning.png]] If you need to import any python modules to use in a *commands*
> section, the import statements **must** appear inline to that function.

## Order Of Command Execution

The order in which package commands are interpreted depends on two factors - the order in which
the packages were requested, and dependencies between packages. This order can be defined as:

* If package *A* was requested before package *B*, then *A*'s commands are interpreted before *B*'s;
* Unless package *A* requires (depends on) *B*, in which case *B* will be interpreted before *A*.

Consider a package *maya_anim_tool*. Let us say this is a maya plugin. Naturally it has a dependency
on *maya*, therefore *maya*'s commands will be interpreted first. This is because the maya plugin
may depend on certain environment variables that *maya* sets. For example, *maya* might initialize
the *MAYA_PLUG_IN_PATH* environment variable, and *maya_anim_tool* may then append to this
variable.

For example, consider the request:

    ]$ rez-env maya_anim_tool-1.3+ PyYAML-3.10 maya-2015

Assuming that *PyYAML* depends on *python*, and *maya_anim_tool* depends on *maya*, then the
resulting *commands* execution order would be:

* maya;
* maya_anim_tool;
* python;
* PyYAML.

## Variable Appending And Prepending

Path-like environment variables can be appended and prepended like so:

    env.PATH.append("{root}/bin")

However, the first append/prepend operation on any given variable actually **overwrites** the
variable, rather than appending. Why does this happen? Consider *PYTHONPATH* - if an initial
overwrite did not happen, then any modules visible on *PYTHONPATH* before the rez environment was
configured would still be there. This would mean you may not have a properly configured
environment. If your system *PyQt* were on *PYTHONPATH* for example, and you used *rez-env* to set
a different *PyQt* version, an attempt to import it within the configured environment would still,
incorrectly, import the system version.

> [[media/icons/info.png]] *PATH* is a special case. It is not simply overwritten, because if that
> happened you would lose important system paths and thus utilities like *ls* and *cd*. In this
> case the system paths are appended back to *PATH* after all commands are interpreted. The system
> paths are defined as the default value of *PATH* in a non-interactive shell.

> [[media/icons/under_construction.png]] Better control over environment variable initialization is
> coming. Specifically, you will be able to specify various modes for variables. For example, one
> mode will append the original (pre-rez) value back to the resulting value.

## String Expansion

### Object Expansion

Any of the objects available to you in a *commands* section can be referred to in formatted strings
that are passed to rex functions such as *setenv* and so on. For example, consider the code:

    appendenv("PATH", "{root}/bin")

Here, "{root}" will expand out to the value of [root](#root), which is the installation path of the
package ("this.root" could also have been used).

You don't *have* to use this feature; it is provided as a convenience. For example, the following
code is equivalent to the previous example, and is just as valid (but more verbose):

    import os.path
    appendenv("PATH", os.path.join(root, "bin"))

Object string expansion is also supported when setting an environment variable via the *env* object:

    env.FOO_LIC = "{this.root}/lic"

### Environment Variable Expansion

Environment variable expansion is also supported when passed to rex functions. The syntaxes *$FOO*
and *${FOO}* are supported, regardless of the syntax supported by the target shell.

### Literal Strings

You can use the [literal](#literal) function to inhibit object- and environment variable- string
expansion. For example, the following code will set the environment variable to the literal string:

    env.TEST = literal("this {root} will not expand")

There is also an expandable function, which matches the default behavior. You wouldn't typically
use this function; however, you can define a string containing literal and expandable parts by
chaining together *literal* and *expandable*:

    env.DESC = literal("the value of {root} is").expandable("{root}")

### Explicit String Expansion

Object string expansion usually occurs **only** when a string is passed to a rex function, or to
the *env* object. For example the simple statement *var = "{root}/bin"* would not expand "{root}"
into *var*. However, you can use the [expandvars](#expandvars) function to enable this behavior
explicitly:

    var = expandvars("{root}/bin")

The *expandvars* and *expandable* functions are slightly different - *expandable* will generate a
shell variable assignment that will expand out; *expandvars* will expand the value immediately.

This table illustrates the difference between *literal*, *expandable* and *expandvars*:

package command                 | equivalent bash command
--------------------------------|------------------------
env.FOO = literal("${USER}")    | export FOO='${USER}'
env.FOO = expandable("${USER}") | export FOO="${USER}"
env.FOO = expandvars("${USER}") | export FOO="jbloggs"

## Pre And Post Commands

Occasionally it's useful for a package to run commands either before or after all other packages,
regardless of the command execution order rules. This can be achieved by defining a *pre_commands*
or *post_commands* function. A package can have any, all or none of *pre_commands*, *commands* and
*post_commands* defined, although it is very common for a package to define just *commands*.

The order of command execution is:

* All package *pre_commands* are executed, in standard execution order;
* Then, all package *commands* are executed, in standard execution order;
* Then, all package *post_commands* are executed, in standard execution order.

## Pre Build Commands

If a package is being built, that package's commands are not run, simply because that package is
not present in its own build environment! However, sometimes there is a need to run commands
specifically for the package being built. For example, you may wish to set some environment
variables to pass information along to the build system.

The *pre_build_commands* function does just this. It is called prior to the build. Note that info
about the current build (such as the installation path) is available in a
[build](#build) object (other commands functions do not have this object visible).

## Pre Test Commands

Sometimes it's useful to perform some extra configuration in the environment that a package's test
will run in. You can define the *pre_test_commands* function to do this. It will be invoked just
before the test is run. As well as the standard [this](#this) object, a [test](#test) object is also
provided to distinguish which test is about to run.

## A Largish Example

Here is an example of a package definition with a fairly lengthy *commands* section:

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

## Objects

Various objects and functions are available to use in the *commands* function (as well as
*pre_commands* and *post_commands*). For example, *env* is a dict-like object that represents all
the environment variables being constructed in the target environment.

Following is a list of the objects and functions available.

### alias
*Function*

    alias("nukex", "Nuke -x")

Create a command alias.

> [[media/icons/info.png]] In *bash*, aliases are implemented as bash functions.

### base
*String*

See [this.base](#thisbase).

### build
*Dict-like object*

    if build.install:
        info("An installation is taking place")

This object is only available in the [pre_build_commands](#pre-build-commands)
function. It has the following fields:

#### build.build_type
*String*

One of 'local', 'central'. The type is _central_ if a package _release_ is occurring, and _local_
otherwise.

#### build.install
*Boolean*

True if an installation is taking place, False otherwise.

#### build.build_path
*String*

Path to the build directory (not the installation path). This will typically reside somewhere
within the `./build` subdirectory of the package being built.

#### build.install_path
Installation directory. Note that this will be set, even if an installation is _not_ taking place.
Do not check this variable to detect if an installation is occurring - see `build.install` instead.

### building
*Boolean*

    if building:
        env.FOO_INCLUDE_PATH = "{root}/include"

This boolean variable is *True* if a build is occurring (typically done via the *rez-build* tool),
and *False* otherwise. Typically a package will use this variable to set environment variables that
are only useful during a build - C++ header include paths are a good example.

### command
*Function*

    command("rm -rf ~/.foo_plugin")

Run an arbitrary shell command. Note that you cannot return a value from this function call, because
*the command has not yet run*. All of the packages in a resolve only have their commands executed
after all packages have been interpreted and converted to the target shell language. Therefore any
value returned from the command, or any side effect the command has, is not visible to any package.

You should prefer to perform simple operations (such as file manipulations and so on) in python
where possible instead. Not only does that take effect immediately, but it's also more cross
platform. For example, instead of running the command above, we could have done this:

    def commands():
        import shutil
        import os.path
        path = os.path.expanduser("~/.foo_plugin")
        if os.path.exists(path):
            shutil.rmtree(path)

### comment
*Function*

    if "nuke" in resolve:
        comment("note: taking over 'nuke' binary!")
        alias("nuke", "foo_nuke_replacer")

Creates a comment line in the converted shell script code. This is only visible if the user views
the current shell's code using the command *"rez-context --interpret"* or looks at the file
referenced by the environment variable *REZ_CONTEXT_FILE*. You would create a comment for debugging
purposes.

### defined
*Function*

    if defined("REZ_MAYA_VERSION"):
        env.FOO_MAYA = 1

Use this boolean function to determine whether or not an environment variable is set.

### env
*Dict-like object*

    env.FOO_DEBUG = 1
    env["BAH_LICENSE"] = "/lic/bah.lic"

The *env* object represents the environment dict of the configured environment. Note that this is
different from the standard python *os.environ* dict, which represents the current environment,
not the one being configured. If a prior package's *commands* set a variable via the *env* object,
it will be visible only via *env*, not *os*. The *os* dict hasn't been updated because the target
configured environment does not yet exist!

The *env* object also provides the following functions:

#### env.append
*Function*

    env.PATH.append("{root}/bin")

Appends a value to an environment variable. By default this will use the *os.pathsep* delimiter
between list items, but this can be overridden using the config setting *env_var_separators*. See
[here](#variable-prepending-and-appending) for further information on the behavior of this function.

#### env.prepend
*Function*

    env.PYTHONPATH.prepend("{root}/python")

like *env.append*, but prepends the environment variable instead.

### ephemerals
*Dict-like object*

    if "foo.cli" in ephemerals:
        info("Foo cli option is being specified!")

A dict representing the list of ephemerals in the resolved environment. Each item is a
string (the full request, eg `.foo.cli-1`), keyed by the ephemeral package name. Note
that you do **not** include the leading `.` when getting items from the `ephemerals`
object.

Use `get_range` to test with the [intersects](Package-Commands#intersects) function.
Here, we enable foo's commandline tools by default, unless explicitly disabled via
a request for `.foo.cli-0`:

    if intersects(ephemerals.get_range("foo.cli", "1"), "1"):
        info("Enabling foo cli tools")
        env.PATH.append("{root}/bin")

### error
*Function*

    if "PyQt" in resolve:
        error("The floob package has problems running in combo with PyQt")

Prints to standard error.

> [[media/icons/info.png]] This function just prints the error, it does not prevent the target
environment from being constructed (use the [stop](#stop) command for that).

### getenv
*Function*

    if getenv("REZ_MAYA_VERSION") == "2016.sp1":
        pass

Gets the value of an environment variable; raises *RexUndefinedVariableError* if not set.

### implicits
*Dict-like object*

    if "platform" in implicits:
        pass

This is similar to the [request](#request) object, but it contains only the package requests as
defined by the [implicit_packages](Configuring-Rez#implicit_packages) configuration setting.

### info
*Function*

    info("floob version is %s" % resolve.floob.version)

Prints to standard out.

### intersects
*Function*

    if intersects(resolve.maya, "2019+"):
        info("Maya 2019 or greater is present")

A boolean function that returns True if the version or version range of the given
object, intersects with the given version range. Valid objects to query include:

* A resolved package, eg `resolve.maya`;
* A package request, eg `request.foo`;
* A version of a resolved package, eg `resolve.maya.version`;
* A resolved ephemeral, eg `ephemerals.foo`;
* A version range object, eg `ephemerals.get_range('foo.cli', '1')`

> [[media/icons/warning.png]] Do **not** do this:
> `if intersects(ephemerals.get("foo.cli", "0"), "1"): ...`
> If 'foo.cli' is not present, this will unexpectedly compare the unversioned
> package named "0" against the version range "1", which will succeed! Use
> `get_range` when testing intersections on the _request_ and _ephemerals_
> objects instead:
> `if intersects(ephemerals.get_range("foo.cli", "0"), "1"): ...`

### literal
*Function*

    env.FOO = literal("this {root} will not expand")

Inhibits expansion of object and environment variable references. You can also chain together
*literal* and *expandable* functions like so:

    env.FOO = literal("the value of {root} is").expandable("{root}")

### request
*Dict-like object*

    if "maya" in request:
        info("maya was asked for!")

A dict representing the list of package requests. Each item is a request string keyed by the
package name. For example, consider the package request:

    ]$ rez-env maya-2015 maya_utils-1.2+<2 !corelib-1.4.4

This request would yield the following *request* object:

    {
        "maya": "maya-2015",
        "maya_utils": "maya_utils-1.2+<2",
        "corelib": "!corelib-1.4.4"
    }

Use `get_range` to test with the [intersects](Package-Commands#intersects) function:

    if intersects(request.get_range("maya", "0"), "2019"):
        info("maya 2019.* was asked for!")

> [[media/icons/info.png]] If multiple requests are present that refer to the same package, the
request is combined ahead of time. In other words, if requests *foo-4+* and *foo-<6* were both
present, the single request *foo-4+<6* would be present in the *request* object.

### resolve
*Dict-like object*

    if "maya" in resolve:
        info("Maya version is %s", resolve.maya.version)
        # ..or resolve["maya"].version

A dict representing the list of packages in the resolved environment. Each item is a
[Package](Package-Definition-Guide) object, keyed by the package name.

### root
*String*

See [this.root](#thisroot).

### setenv
*Function*

    setenv("FOO_PLUGIN_PATH", "{root}/plugins")

This function sets an environment variable to the given value. It is equivalent to setting a
variable via the *env* object (eg, "env.FOO = 'BAH'").

### source
*Function*

    source("{root}/scripts/init.sh")

Source a shell script. Note that, similarly to *commands*, this function cannot return a value, and
any side effects that the script sourcing has is not visible to any packages. For example, if the
*init.sh* script above contained *"export FOO=BAH"*, a subsequent test for this variable on the
*env* object would yield nothing.

### stop
*Function*

    stop("The value should be %s", expected_value)

Raises an exception and stops a resolve from completing. You should use this when an unrecoverable
error is detected and it is not possible to configure a valid environment.

### system
*System object*

    if system.platform == "windows":
        ...

This object provided system information, such as current platform, arch and os. See
[the source](https://github.com/nerdvegas/rez/blob/master/src/rez/system.py) for more info.

### test
*Dict-like object*

    if test.name == "unit":
        info("My unit test is about to run yay")

This object is only available in the [pre_test_commands](#pre-test-commands) function. It has the
following fields:

#### test.name
*String*

Name of the test about to run.

### this
*Package object*

    import os.path
    env.PATH.append(os.path.join(this.root, "bin"))

The *this* object represents the current package. The following attributes are most commonly used
in a *commands* section (though you have access to all package attributes - see
[here](Package-Definition-Guide)):

#### this.base
*String*

Similar to *this.root*, but does not include the variant subpath, if there is one. Different
variants of the same package share the same *base* directory. See [here](Variants) for more
information on package structure in relation to variants.

#### this.name
*String*

The name of the package, eg 'houdini'.

#### this.root
*String*

The installation directory of the package. If the package contains variants, this path will include
the variant subpath. This is the directory that contains the installed package payload. See
[here](Variants) for more information on package structure in relation to variants.

#### this.version
*Version object*

The package version. It can be used as a string, however you can also access specific tokens in the
version (such as major version number and so on), as this code snippet demonstrates:

    env.FOO_MAJOR = this.version.major  # or, this.version[0]

The available token references are *this.version.major*, *this.version.minor* and
*this.version.patch*, but you can also use a standard list index to reference any version token.

### undefined
*Function*

    if undefined("REZ_MAYA_VERSION"):
        info("maya is not present")

Use this boolean function to determine whether or not an environment variable is set. This is the
opposite of [defined](#defined).

### unsetenv
*Function*

    unsetenv("FOO_LIC_SERVER")

Unsets an environment variable. This function does nothing if the environment variable was not set.

### version
*Version object*

See [this.version](#thisversion).
