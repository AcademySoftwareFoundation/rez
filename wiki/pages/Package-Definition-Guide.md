## Overview

Packages are defined by a *package definition file*. This is typically a file named *package.py*
that is located in the root directory of each package install. For example, given package
repository location */packages/inhouse*, the package definition file for package "foo-1.0.0" would
be */packages/inhouse/foo/1.0.0/package.py*.

Here is an example package definition file:

    name = 'sequence'

    version = '2.1.2'

    description = 'Sequence detection library.'

    authors = ['ajohns']

    tools = [
        'lsq',
        'cpq'
    ]

    requires = [
        'python-2.6+<3',
        'argparse'
    ]

    def commands():
        env.PATH.append("{root}/bin")
        env.PYTHONPATH.append("{root}/python")

    uuid = '6c43d533-92bb-4f8b-b812-7020bf54d3f1'

## Package Attributes

Every variable defined in the package definition file becomes an attribute on the built or
installed package. This includes attributes that are not in the
[standard list](#standard-package-attributes) - you can add any custom attribute to a package.

Some variables are not, however, added as package attributes. Consider the following package
definition snippet:

    import sys

    description = "This package was built on %s" % sys.platform

Here we do not want *sys* to become a package attribute, because providing a python module as a
package attribute is nonsensical.

Python variables that do **not** become package attributes include:

* Python modules;
* Functions, not include early- and late- binding functions (see next), and not including the
  *commands* and related functions;
* Any variable with a leading double underscore;
* Any variable that is a [build-time package attribute](#build-time-package-attributes).

## Package Attributes As Functions

Package attributes can be implemented as functions - the return value of the function becomes
the attribute value. There are two types of attribute functions - *early binding* functions,
and *late binding* functions - and these are decorated using *@early* and *@late* respectively.

> [[media/icons/warning.png]] The *commands* functions are an exception to the rule. They are
> late bound, but are not the same as a standard function attribute, and are *never* decorated
> with the early or late decorators.

### Early Binding Functions

Early binding functions use the *@early* decorator. They are evaluated at *build time*, hence the
'early' in 'early binding'. Any package attribute can be implemented as an early binding function.

Here is an example of an *authors* attribute that is automatically set to the contributors of the
package's git project:

    @early()
    def authors():
        import subprocess
        p = subprocess.Popen("git shortlog -sn | cut -f2",
                             shell=True, stdout=subprocess.PIPE)
        out, _ = p.communicate()
        return out.strip().split('\n')

> [[media/icons/info.png]] You can assume that during evaluation of early binding functions, the
> current working directory is the root directory containing your *package.py*.

An early bound function can also have access to other package attributes. To do this, use the
implicit *this* object:

    @early()
    def description():
        # a not very useful description
        return "%s version %s" % (this.name, this.version)

> [[media/icons/warning.png]] Do not reference other early bound or late bound attributes in
> your early bound function - an error will be raised if you do.

Early binding functions are a convenience - you can always use an arbitrary function instead, like so:

    def _description():
        return "%s version %s" % (this.name, this.version)

    description = _description()

However, using early binding results in a package definition that is cleaner and more explicit - it
is clear that an attribute is intended to be evaluated at build time, and you avoid the need to
define an arbitrary function earlier in the python source. You can always use a combination of the
two as well - an early binding function can call an arbitrary function defined at the bottom of
your definition file.

#### Available Objects

Following is the list of objects that are available during early evaluation.

* *building* - see [building](Package-Commands#building);
* *build_variant_index* - the index of the variant currently being built. This is only relevant if
  `building` is True.
* *build_variant_requires* - the subset of package requirements specific to the variant
  currently being built. This is a list of `PackageRequest` objects. This is only relevant if
  `building` is True.
* *this* - the current package, as described previously.

Be aware that early-bound functions are actually evaluated multiple times during a build - once
pre-build, and once per variant, during its build. This is necessary in order for early-bound
functions to change their return value based on variables like `build_variant_index`. Note that the
*pre-build* evaluated value is the one set into the installed package, and in this case, `building`
is False.

An example of where you'd need to be aware of this is if you wanted the `requires` field to include
a certain package at runtime only (ie, not present during the package build). In this case, `requires`
might look like so:

    @early()
    def requires():
        if building:
            return ["python-2"]
        else:
            return ["runtimeonly-1.2", "python-2"]

> [[media/icons/warning.png]] You **must** ensure that your early-bound function returns the value
> you want to see in the installed package, when `building` is False.

### Late Binding Functions

Late binding functions stay as functions in the installed package definition, and are only evaluated
lazily, when the attribute is accessed for the first time (the return value is then cached).

Not any attribute can be implemented as a late binding function. The allowed attributes are:

* requires
* build_requires
* private_build_requires
* tools
* help
* any arbitrary attribute

Here is an example of a late binding *tools* attribute:

    @late()
    def tools():
        import os

        # get everything in bin dir
        binpath = os.path.join(this.root, "bin")
        result = os.listdir(binpath)

        # we don't want artists to see the admin tools
        if os.getenv("_USER_ROLE") != "superuser":
            result = set(result) - set(["delete-all", "mod-things"])

        return list(result)

> [[media/icons/warning.png]] Late binding function attributes *must* perform any necessary imports
> *within* the function, not at the top of the *package.py* file.

Note that, if this function just returned the binaries found in the bin dir, it would have made
more sense to implement this as an *early binding* function - no code evaluation has to happen at
runtime then, so it's cheaper. However here a modification is made based on the value of the
*_USER_ROLE* environment variable, which isn't known at build time.

If some information for an attribute could be calculated once at build time, you can reduce the
runtime cost by storing that part into an early binding arbitrary attribute. For example, we could
reimplement the above example like so:

    @late()
    def tools():
        import os
        result = this._tools

        # we don't want artists to see the admin tools
        if os.getenv("_USER_ROLE") != "superuser":
            result = set(result) - set(["delete-all", "mod-things"])

        return list(result)

    @early()
    def _tools():
        import os
        return os.listdir("./bin")

Note how in the *_tools* function we're referring to a relative path. Remember that early binding
functions are evaluated at build time - the package hasn't actually been built or installed yet,
so attributes such as *this.root* don't exist.

#### The *in_context* Function

When late binding functions are evaluated, a boolean function *in_context* is present, which
returns True if the package is part of a resolved context, or False otherwise. For example,
if you just use the rez API to iterate over packages (as the *rez-search* tool does), these
packages do not belong to a context; however if you create a *ResolvedContext* object (as
the *rez-env* tool does) and iterate over its resolved packages, these belong to a context.

The in-context or not-in-context distinction is important, because often the package attribute
will need information from the context to give desired behavior. For example, consider the
late binding *tool* attribute below:

    @late()
    def tools():
        result = ["edit"]

        if in_context() and "maya" in request:
            result.append("maya-edit")

        return result

Here the *request* object is being checked to see if the *maya* package was requested in the
current env; if it was, a maya-specific tool *maya-edit* is added to the tool list.

> [[media/icons/warning.png]] Always ensure your late binding function returns a sensible
> value regardless of whether *in_context* is True or False. Otherwise, simply trying to
> query the package attributes (using *rez-search* for example) may cause errors.

#### Available Objects

Following is the list of objects that are available during late evaluation, if *in_context*
is *True*:

* *context* - the *ResolvedContext* instance this package belongs to;
* *system* - see [system](Package-Commands#system);
* *building* - see [building](Package-Commands#building);
* *request* - see [request](Package-Commands#request);
* *implicits* - see [implicits](Package-Commands#implicits).

The following objects are available in *all* cases:

* *this* - the current package/variant (see note below);
* *in_context* - the *in_context* function itself.

> [[media/icons/warning.png]] The *this* object may be either a package or a variant,
> depending on the situation. For example, if *in_context* is True, then *this* is a
> variant, because variants are the objects present in a resolved context. On the other
> hand, if a package is accessed via API (for example, by using the *rez-search* tool),
> then *this* may be a package. The difference matters, because variants have some
> attributes that packages don't - notably, *root* and *index*. Use the properties
> `this.is_package` and `this.is_variant` to distinguish the case if needed.

#### Example - Late Bound build_requires

Here is an example of a package.py with a late-bound `build_requires` field:

    name = "maya_thing"

    version = "1.0.0"

    variants = [
        ["maya-2017"],
        ["maya-2018"]
    ]

    @late()
    def build_requires():
        if this.is_package:
            return []
        elif this.index == 0:
            return ["maya_2017_build_utils"]
        else:
            return ["maya_2018_build_utils"]

Note the check for `this.is_package`. This is necessary, otherwise the evaluation would
fail in some circumstances. Specifically, if someone ran the following command, the `this`
field would actually be a `Package` instance, which doesn't have an `index`:

    ]$ rez-search maya_thing --type package --format '{build_requires}'

In this case, `build_requires` is somewhat nonsensical (there is no common build requirement
for both variants here), but something needs to be returned nonetheless.

## Sharing Code Across Package Definition Files

It is possible to share common code across package definition function attributes, but the
mechanism that is used is different depending on whether a function is early binding or late
binding. This is to avoid installed packages being dependent on external code that may change
at any time; builds being dependent on external code is not problematic however.

### Sharing Code During A Build

Functions in a *package.py* file which are evaluated at build time include:

* The *preprocess* function;
* Any package attribute implemented as a function using the *@early* decorator.

You expose common code to these functions by using the
[package_definition_build_python_paths](Configuring-Rez#package_definition_build_python_paths)
config setting.

### Sharing Code Across Installed Packages

Functions that are evaluated in installed packages' definition files include:

* The various *commands* functions;
* Any package attribute implemented as a function using the *@late* decorator.

You expose common code to these functions by using the *@include* decorator, which relies on the
[package_definition_python_path](Configuring-Rez#package_definition_python_path) config setting.
The module source files are actually copied into each package's install payload, so the package
stays self-contained, and will not break or change behavior if the original modules' source
files are changed. The downside though, is that these modules are not imported, and they themselves
cannot import other modules managed in the same way.

Here is an example of a package's *commands* using a shared module:

    # in package.py
    @include("utils")
    def commands():
        utils.set_common_env_vars(this, env)

## Requirements Expansion

Often a package may be compatible with a broader range of its dependencies at build time than it is
at runtime. For example, a C++ package may build against any version of *boost-1*, but may
then need to link to the specific minor version that it was built against, say *boost-1.55*.

You can describe this in your package's *requires* attribute (or any of the related attributes,
such as *build_requires*) by using wildcards as shown here:

    requires = [
        "boost-1.*"
    ]

If you check the *package.py* of the built package, you will see that the boost reference in the
requires list will be expanded to the latest found within the given range ("boost-1.55" for example).

There is also a special wilcard available - *"**"*. This expands to the full package version. For
example, the requirement *boost-1.*** might expand to *boost-1.55.1*.

You can also achieve requirements expansion by implementing *requires* as an early binding
function (and you may want to use some variation of this to generate *variants* for example), and
using the rez *expand_requires* function:

    @early()
    def requires():
        from rez.package_py_utils import expand_requires
        return expand_requires(["boost-1.*"])

## Package Preprocessing

You can define a *preprocessing* function either globally or in a *package.py*. This can be used to
validate a package, or even change some of its attributes, before it is built. To set a global
preprocessing function, see the
[package_preprocess_function](Configuring-Rez#package_preprocess_function) config setting.

Consider the following preprocessing function, defined in a *package.py*:

    def preprocess(package, data):
        from rez.package_py_utils import InvalidPackageError
        import re

        if not re.match("[a-z]+$", package.name):
            raise InvalidPackageError("Invalid name, only lowercase letters allowed")

        if not package.authors:
            from preprocess_utils import get_git_committers
            data["authors"] = get_git_committers()

This preprocessor checks the package name against a regex; and sets the package authors list to its
git committers, if not already supplied in the *package.py*. To update package attributes, you have
to update the given *data* dict, *not* the *package* instance.

To halt a build because a package is not valid, you must raise an *InvalidPackageError* as shown
above.

> [[media/icons/info.png]] To see the preprocessed contents of a package.py, run the command
> *"rez-build --view-pre"* in the source root directory. This will just print the preprocessed
> package to standard out, then exit.

### Overriding Config Settings In Preprocessing

It is not uncommon to override config settings such as the release path in a package, like so:

    # in package.py
    with scope("config") as c:
        c.release_packages_path = "/software/packages/external"

Let's say we have a scenario where we want to install third party packages to a specific install
path, and that we set the arbitrary attribute *external* to True for these packages. We could do
this with a global preprocessing function like this:

    def preprocess(package, data):
        if not data.get("external"):
            return

        try:
            _ = data["config"]["release_packages_path"]
            return  # already explicitly specified by package
        except KeyError:
            pass

        data["config"] = data["config"] or {}
        data["config"]["release_packages_path"] = "/software/packages/external"

The *"with scope(...)"* statement is just a fancy way of defining a dict, so you can do the same
thing in the preprocess function simply by updating the *config* dict within *data*.

## Example Package

Here is an example package definition, demonstrating several features. This is an example of a
python package which, instead of actually installing python, detects the existing system python
installation instead, and binds that into a rez package.

    name = "python"

    @early()
    def version():
        return this.__version + "-detected"

    authors = [
        "Guido van Rossum"
    ]

    description = \
        """
        The Python programming language.
        """

    @early()
    def variants():
        from rez.package_py_utils import expand_requires
        requires = ["platform-**", "arch-**", "os-**"]
        return [expand_requires(*requires)]

    @early()
    def tools():
        version_parts = this.__version.split('.')

        return [
            "2to3",
            "pydoc",
            "python",
            "python%s" % (version_parts[0]),
            "python%s.%s" % (version_parts[0], version_parts[1])
        ]

    uuid = "recipes.python"

    def commands():
        env.PATH.append("{this._bin_path}")

        if building:
            env.CMAKE_MODULE_PATH.append("{root}/cmake")

    # --- internals

    def _exec_python(attr, src):
        import subprocess

        p = subprocess.Popen(
            ["python", "-c", src],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()

        if p.returncode:
            from rez.exceptions import InvalidPackageError
            raise InvalidPackageError(
                "Error determining package attribute '%s':\n%s" % (attr, err))

        return out.strip()

    @early()
    def _bin_path():
        return this._exec_python(
            "_bin_path",
            "import sys, os.path; print(os.path.dirname(sys.executable))")

    def _version():
        return _exec_python(
            "version",
            "import sys; print(sys.version.split()[0])")

    __version = _version()

Note the following:

* *variants* is implemented as an early bound attribute, and uses *requirements expansion* to
  dynamically define the variant requirements. Even though only the *requires* and related attributes
  natively expand wildcards, you can still use the *expand_requirement* function yourself, as
  illustrated here.
* A *_version* function has been defined, and its return value stored into the *__version* variable.
  This is done because two other early binding attributes - *version* and *tools* - use this value,
  and we avoid calling the function twice. Both *_version* and *__version* are later stripped from
  the package, because one is a normal function, and the other has double leading underscores.
* An arbitrary attribute *_bin_path* has been defined, and implemented as an early bound attribute.
  The *commands* function then uses this value. In this example, it was far better to take this
  approach than the alternative - running the python subprocess in the *commands* function. Doing that
  would have been very costly, since commands are executed every time a new environment is created
  (and launching a subprocess is slow). Instead, here we take this cost at build time, and cache the
  result into the package attribute.
* Common code was provided in the normal function *_exec_python*, which will be stripped from the
  installed package.

## Standard Package Attributes

Following is a list, in alphabetical order, of every standard attribute that a user can define in a
package definition file (you can also define your own arbitrary attributes). Each entry specifies
the data type, and includes a code snippet.

### authors
*List of string*

    authors = ["jchrist", "sclaus"]

Package authors. Should be in order, starting with the major contributor.

### build_requires
*List of string*

    build_requires = [
        "cmake-2.8",
        "doxygen"
    ]

This is the same as *requires*, except that these dependencies are only included during a build
(typically invoked using the *rez-build* tool).

### cachable
*Boolean*

    cachable = True

Determines whether a package can be cached when [package caching](Package-Caching#Overview) is
enabled. If not provided, this is determined from the global config setting [default_cachable](Configuring-Rez#default_cachable) and related `default_cachable_*` settings.

### commands
*Function*

    def commands():
        env.PYTHONPATH.append("{root}/python")
        env.PATH.append("{root}/bin")

This is a block of python code which tells rez how to update an environment so that this package can
be used. There is a python API provided (see [here](Package-Commands) for more details) that lets
you do things such as:

* set, unset, prepend and append environment variables;
* create aliases;
* source scripts;
* print messages.

In this example, the 'foo' package is appending a path to *PYTHONPATH*, and appending a path to
*PATH*. The special string "{root}" will expand out to the install location of the package. This is
a fairly typical example.

### config

    with scope("config"):
        release_packages_path = "/software/packages/apps"

Packages are able to override rez configuration settings. This is useful in some cases; for example,
we may want a package to release to a different directory than the default (as this example shows).
See [here](Configuring-Rez) for more details.

### description
*String*

    description = "Library for communicating with the dead."

This is a general description of the package. It should not mention details about a particular
version of the package, just about the package in general.

### has_plugins
*Boolean*

    has_plugins = True

Indicates that the package is an application that may have plugins. These plugins are often made
available as rez packages also.

### hashed_variants
*Boolean*

    hashed_variants = True

Instructs the package to install variants into a subdirectory based on a hash of the variant's
contents (its requirements in other words). This is useful for variants with a high number of
requirements, or with requirements that do not translate well to directories on the filesystem
(such as conflict requirements).

### help
*String or List of String*

    help = "https://github.com/nerdvegas/rez/wiki"

URL for package webpage, or, if a string containing spaces, a command to run. You can show the help
for a package using the *rez-help* command line tool. If this value is a list, then this represents
multiple help entries, and you can specify the entry you want to see using the `SECTION` argument.

### name
*String (mandatory)*

    name = "maya_utils"

This is the name of the package. Alphanumerics and underscores are allowed. Name is case sensitive.

### plugin_for
*String*

    plugin_for = "maya"

Provided if this package is a plugin of another package. For example, this might be a maya plugin.

### post_commands
*Function*

    def post_commands():
        env.FOO_PLUGIN_PATH.append("@")

Similar to *pre_commands*, but runs in a final phase rather than the first. See that attribute for
further details.

### pre_commands
*Function*

    def pre_commands():
        import os.path
        env.FOO_PLUGIN_PATH = os.path.join(this.root, "plugins")

This is the same as *commands*, except that all packages' *pre_commands* are executed in a first
pass; then, all *commands* are run in a second; and lastly, *post_commands* are all run in a third
phase. It is sometimes useful to ensure that some of a package's commands are run before, or after
all others, and using pre/post_commands is a way of doing that.

### pre_test_commands
*Function*

    def pre_test_commands():
        if test.name == "unit":
            env.IS_UNIT_TEST = 1

This is similar to *commands*, except that it is run prior to each test defined in
[tests](#tests)
See [here](Package-Commands#pre-test-commands) for more details.

### relocatable
*Boolean*

    relocatable = True

Determines whether a package can be copied to another package repository (using the `rez-cp` tool for
example). If not provided, this is determined from the global config setting [default_relocatable](Configuring-Rez#default_relocatable) and related `default_relocatable_*` settings.

### requires
*List of string*

    requires = [
        "python-2",
        "maya-2016",
        "maya_utils-3.4+<4"
    ]

This is a list of other packages that this package depends on. A rez package should list all the
packages it needs - someone should be able to use your package without needing to know about how it
works internally - and this includes needing to know its dependencies.

Rez has a syntax for these package requests. For example, "python-2.6" is a package request which
covers the range of all python packages starting with 2.6 - for example, "python-2.6.0",
"python-2.6.4" (it is not simply a prefix - "python-2.65" is not within the request). When you
request a package, you are asking rez for any version within this request, although rez will aim to
give you the latest possible version.

For more details on request syntax, see [here](Basic-Concepts#package-requests).

### tests
*Dict*

    tests = {
        "unit": "python -m unittest discover -s {root}/python/tests",
        "lint": {
            "command": "pylint mymodule",
            "requires": ["pylint"],
            "run_on": ["default", "pre_release"]
        },
        "maya_CI": {
            "command": "python {root}/ci_tests/maya.py",
            "on_variants": {
                "type": "requires",
                "value": ["maya"]
            },
            "run_on": "explicit"
        }
    }

This is a dict of tests that can be run on the package using the *rez-test* tool. For example, to
run a linter on the package *maya_utils* with the *test* attribute above, you would simply run:

    ]$ rez-test maya_utils lint

If a test entry is a string or list of strings, this is interpreted as the command to run. Command
strings will expand any references to package attributes, such as *{root}*.

If you provide a nested dict, you can specify extra fields per test, as follows:

* **requires**: Extra package requirements to include in the test's runtime env.
* **run_on**: When to run this test. Valid values are:
  * `default` (the default): Run when `rez-test` is run with no `TEST` args specified.
  * `pre_install`: Run before an install (ie `rez-build -i`), and abort the install on fail.
  * `pre_release`: Run before a release, and abort the release on fail.
  * `explicit`: Only run if specified as `TEST` when `rez-test` is run.
* **on_variants**: Which variants the test should be run on. Valid values are:
  * True: Run the test on all variants.
  * False (the default): Run the test only on one variant (ie the variant you get by
    default when the test env is resolved). This is useful for tests like linting,
    where variants may be irrelevant.
  * A dict. This is a variant selection mechanism. In the example above, the "maya_CI" test will
    run only on those variants that directly require `maya` (or a package within this range, eg
    `maya-2019`). Note that "requires" is the only filter type currently available.

### tools
*List of string*

    tools = [
        "houdini",
        "hescape",
        "hython"
    ]

This is a list of tools that the package provides. This entry is important later on when we talk
about [suites](Suites#suite-tools).

### uuid
*String*

    uuid = "489ad32867494baab7e5be3e462473c6"

This string should uniquely identify this *package family* - in other words, all the versions of a
particular package, such as 'maya'. It is used to detect the case where two unrelated packages that
happen to have the same name are attempted to be released. If rez detects a uuid mismatch, it will
abort the release.

You should set the uuid on a new package once, and not change it from then on. The format of the
string doesn't actually matter, but you'd typically use a true UUID, and you can generate one
like so:

    ]$ python -c 'import uuid; print(uuid.uuid4().hex)'

### variants
*List of list of string*

    variants = [
        ["maya-2015.3"],
        ["maya-2016.1"],
        ["maya-2016.7"]
    ]

A package can contain *variants* - think of them as different flavors of the same package version,
but with differing dependencies. See the [variants chapter](Variants) for further details.

### version
*String*

    version = "1.0.0"

This is the version of the package. See [here](Basic-Concepts#versions) for further details on valid
package versions.


## Build Time Package Attributes

The following package attributes only appear in packages to be built; they are stripped from the
package once installed because they are only used at build time.

### build_command
*String or False*

    build_command = "bash {root}/build.sh {install}"

Package build command. If present, this is used as the build command when *rez-build* is run,
rather than detecting the build system from present build scripts (such as *CMakeLists.txt*). If
*False*, this indicates that no build step is necessary (the package definition will still be
installed, and this is enough to define the package).

The *{root}* string expands to the root directory of the package (where the package.py is
contained). Note that, like all builds, the working directory is set to the *build path*, which
is typically somewhere under a *build* subdirectory, and is where build outputs should go.

The *{install}* string expands to "*install*" if an installation is occurring, or the empty string
otherwise. This is useful for passing the install target directly to the command (for example, when
using *make*) rather than relying on a build script checking the *REZ_BUILD_INSTALL* environment
variable.

The full set of variables that can be referenced in the build command are:

    * *root*: (see above);
    * *install*: (see above)
    * *build_path*: The build path (this will also be the current working directory);
    * *install_path*: Full path to install destination;
    * *name*: Name of the package getting built;
    * *variant_index*: Index of the current variant getting built, or an empty
      string ('') if no variants are present.
    * *version*: Package version currently getting built.

### build_system
*String*

    build_system = "cmake"

Specify the build system used to build this package. If not set, it is detected automatically when
a build occurs (or the user specifies it using the `--build-system` option).

### pre_build_commands
*Function*

    def pre_build_commands():
        env.FOO_BUILT_BY_REZ = 1

This is similar to *commands*, except that it is run _prior to the current package being built_.
See [here](Package-Commands#pre-build-commands) for more details.

### preprocess
*Function*

See [Package Preprocessing](#package-preprocessing)

### private_build_requires
*List of string*

    private_build_requires = [
        "cmake-2.8",
        "doxygen"
    ]

This is the same as *build_requires*, except that these dependencies are only included if this
package is being built. Contrast this with *build_requires*, whose dependencies are included if a
build is occurring - regardless of whether this package specifically is being built, or whether
this package is a dependency of the package being built.

### requires_rez_version
*String*

    requires_rez_version = "2.10"

This defines the minimum version of rez needed to build this package. New package features have
been added over time, so older rez versions cannot necessarily build newer packages.

## Release Time Package Attributes

The following package attributes are created for you by Rez when your package is released via the
*rez-release* tool. If you look at the released *package.py* file you will notice that some or all
of these attributes have been added.

### changelog
*String*

    changelog = \
        """
        commit 22abe31541ceebced8d4e209e3f6c44d8d0bea1c
        Author: allan johns <nerdvegas at gee mail dot com>
        Date:   Sun May 15 15:39:10 2016 -0700

            first commit
        """

Change log containing all commits since the last released package. If the previous release was from
a different branch, the changelog given will go back to the last common commit ancestor. The syntax
of this changelog depends on the version control system; the example here is from a *git*-based
package.

### previous_revision
*Type varies*

Revision information of the previously released package, if any (see *revision* for code example -
the code for this attribute is the same).

### previous_version
*String*

    previous_version = "1.0.1"

The version of the package previously released, if any.

### release_message
*String*

    release_message = "Fixed the flickering thingo"

The package release message. This is supplied either via the *rez-release* tool's *--message*
option, or was entered in a text editor on release if rez is configured to do this (see the config
setting 'TODO_ADD_THIS'). A package may not have a release message.

### revision
*Type varies*

    revision = \
        {'branch': 'master',
         'commit': '22abe31541ceebced8d4e209e3f6c44d8d0bea1c',
         'fetch_url': 'git@github.com:nerdvegas/dummy.git',
         'push_url': 'git@github.com:nerdvegas/dummy.git',
         'tracking_branch': 'origin/master'}

Information about the source control revision containing the source code that was released. The
data type is determined by the version control system plugin that was used. The example code shown
here is the revision dict from a *git*-based package.

### timestamp
*Integer*

    timestamp = 1463350552

Epoch time at which the package was released.

### vcs
*String*

    vcs = "git"

Name of the version control system this package was released from.
