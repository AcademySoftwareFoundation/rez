## Overview

Rez packages can be built and locally installed using the *rez-build* tool. This
tool performs the following actions:

* Iterates over a package's [variants](Variants);
* Constructs the build environment;
* Runs the build system within this environment.

Each build occurs within a *build path* - this is typically either a *build*
subdirectory, or a variant-specific subdirectory under *build*. For example, a
package with two python-based variants might look like this:

    +- package.py
    +- CMakeLists.txt (or other build file)
    +-build
      +-python-2.6  # build dir for python-2.6 variant
      +-python-2.7  # build dir for python-2.6 variant

The current working directory is set to the *build path* during a build.

## The Build Environment

The build environment is a rez resolved environment. Its requirement list is
constructed like so:

* First, the package's [requires](Package-Definition-Guide#requires) list is used;
* Then, the package's [build_requires](Package-Definition-Guide#build_requires) is
  appended. This is transitive - the *build_requires* of all other packages in the
  environment are also used;
* Then, the package's [private_build_requires](Package-Definition-Guide#private-build_requires)
  is appended (unlike *build_requires*, it is not transitive).
* Finally, if the package has variants, the current variant's requirements are
  appended.

A standard list of environment variables is also set (all prefixed with *REZ_BUILD_*) -
you can see the full list [here](Environment-Variables#resolved-build-environment-variables).

The build system is then invoked within this environment, for each variant.

## Build Time Dependencies

Sometimes it is desirable for a package to depend on another package only for the purposes
of building its code, or perhaps generating documentation. Let’s use documentation as an
example - a C++ project may need to builds its docs using doxygen, but once the docs are
generated, doxygen is no longer needed.

This is achieved by listing build-time dependencies under a
[build_requires](Package-Definition-Guide#build_requires) or
[private_build_requires](Package-Definition-Guide#private-build_requires)
section in the *package.py*. The requirements in *private_build_requires* are only used
from the package being built; requirements from *build_requires* however are transitive - build
requirements from all packages in the build environment are included.

Some example *private_build_requires* use cases include:

* Documentation generators such as *doxygen* or *sphinx*;
* Build utilities. For example, you may have a package called *pyqt_cmake_utils*, which
  provides cmake macros for converting *ui* files to *py*;
* Statically linked libraries (since the library is linked at build time, the package
  is not needed at runtime).

An example use case of *build_requires* is a header-only (hpp) C++ library - if your own
C++ package includes this library in its own headers, other packages will also need this
library at build time (since they may include your headers, which in turn include the
hpp headers).

## Package Communication

Let's say I have two C++ packages, *maya_utils* and the well-known *boost* library. How
does *maya_utils* find *boost*'s header files, or library files?

The short answer is, that is entirely up to you. Rez is not actually a build system -
it supports various build systems (as the next section describes), and it configures the
build environment, but the details of the build itself are left open for the user.
Having said that, *cmake* has been supported by rez for some time, and rez comes with a
decent amount of utility code to manage cmake builds.

When a rez environment is configured, each package's [commands](Package-Definition-Guide#commands)
section configures the environment. When a build is occurring, a special variable
[building](Package-Commands#building) is set to *True*. Your packages should use this
variable to communicate build information to the package being built.

For example, our *boost* package's commands might look like so:

    def commands():
        if building:
            # there is a 'FindBoost.cmake' file in this dir..
            env.CMAKE_MODULE_PATH.append("{root}/cmake")

A (very simple) *FindBoost.cmake* file might look like this:

    set(Boost_INCLUDE_DIRS $ENV{REZ_BOOST_ROOT}/include)
    set(Boost_LIBRARY_DIRS $ENV{REZ_BOOST_ROOT}/lib)
    set(Boost_LIBRARIES boost-python)

Then, our *maya_utils* package might have a *CMakeLists.txt* file (cmake's build script)
containing:

    find_package(Boost)
    include_directories(${Boost_INCLUDE_DIRS})
    link_directories(${Boost_LIBRARY_DIRS})
    target_link_libraries(maya_utils ${Boost_LIBRARIES})

As it happens, the [find_package](https://cmake.org/cmake/help/v3.0/command/find_package.html)
cmake macro searches the paths listed in the *CMAKE_MODULE_PATH* environment variable,
and looks for a file called *FindXXX.cmake*, where *XXX* is the name of the package (in this
case, *Boost*), which it then includes.

## The Build System

Rez supports multiple build systems, and new ones can be added as plugins. When a
build is invoked, the build system is detected automatically. For example, if a
*CMakeLists.txt* file is found in the package's root directory, the *cmake* build
system is used.

### Argument Passing

There are two ways to pass arguments to the build system.

First, some build system plugins add extra options to the *rez-build* command directly.
For example, if you are in a CMake-based package, and you run *rez-build -h*, you will
see cmake-specific options listed, such as *--build-target*.

Second, you can pass arguments directly to the build system - either using the
*rez-build* *--build-args* option; or listing the build system arguments after *--*.

For example, here we explicitly define a variable in a cmake build:

    ]$ rez-build -- -DMYVAR=YES

### Custom Build Commands

As well as detecting the build system from build files, a package can explicitly
specify its own build commands, using the
[build_command](Package-Definition-Guide#build_command) package attribute. If present,
this takes precedence over other detected build systems.

For example, consider the following *package.py* snippet:

    name = "nuke_utils"

    version = "1.2.3"

    build_command = "bash {root}/build.sh {install}"

When *rez-build* is run on this package, the given *build.sh* script will be executed
with *bash*. The *{root}* string expands to the root path of the package (the same
directory containing *package.py*). The *{install}* string expands to "*install*" if
an install is occurring, or the empty string otherwise. This is useful for passing the
install target directly to the command (for example, when using *make*) rather than
relying on a build script checking the *REZ_BUILD_INSTALL* environment variable.

> [[media/icons/warning.png]] The current working directory during a build is set
> to the *build path*, **not** to the package root directory. For this reason, you
> will typically use the *{root}* string to refer to a build script in the package's
> root directory.

#### Passing Arguments

You can add arguments for your build script to the *rez-build* command directly, by
providing a *parse_build_args.py* source file in the package root. Here is an example:

    # in parse_build_args.py
    parser.add_argument("--foo", action="store_true", help="do some foo")

Now if you run *rez-build -h* on this package, you will see the option listed:

    $ rez-build -h
    usage: rez build [-h] [-c] [-i] [-p PATH] [--fail-graph] [-s] [--view-pre]
                     [--process {remote,local}] [--foo]
                     [--variants INDEX [INDEX ...]] [--ba ARGS] [--cba ARGS] [-v]

    Build a package from source.

    optional arguments:
      ...
      --foo                 do some foo

The added arguments are stored into environment variables so that your build script
can access them. They are prefixed with *__PARSE_ARG_*; in our example above, the
variable *__PARSE_ARG_FOO* will be set. Booleans will be set to 0/1, and lists are
space separated, with quotes where necessary.

#### Make Example

Following is a very simple C++ example, showing how to use a custom build command to
build and install via *make*:

    # in package.py
    build_command = "make -f {root}/Makefile {install}"


    # in Makefile
    hai: ${REZ_BUILD_SOURCE_PATH}/lib/main.cpp
        g++ -o hai ${REZ_BUILD_SOURCE_PATH}/lib/main.cpp

    .PHONY: install
    install: hai
        mkdir -p ${REZ_BUILD_INSTALL_PATH}/bin
        cp $< ${REZ_BUILD_INSTALL_PATH}/bin/hai

## Local Package Installs

After you've made some code changes, you presumably want to test them. You do this
by *locally installing* the package, then resolving an environment with *rez-env*
to test the package in. The cycle goes like this:

* Make code changes;
* Run *rez-build --install* to install as a local package;
* Run *rez-env mypackage* in a separate shell. This will pick up your local package,
  and your package requirements;
* Test the package.

A local install builds and installs the package to the *local package repository*,
which is typically the directory *~/packages* (see [here](Configuring-Rez#local_packages_path)).
This directory is listed at the start of the
[package search path](Basic-Concepts#package-search-path), so when you resolve an
environment to test with, the locally installed package will be picked up first. Your
package will typically be installed to *~/packages/packagename/version*, for example
*~/packages/maya_utils/1.0.5*. If you have variants, they will be installed into subdirectories
within this install path (see [here](Variants#disk-structure) for more details).

> [[media/icons/info.png]] You don't need to run *rez-env* after every install. If your
> package's requirements haven't changed, you can keep using the existing test environment.

You can make sure you've picked up your local package by checking the output of the
*rez-env* call:

    ]$ rez-env sequence

    You are now in a rez-configured environment.

    resolved by ajohns@turtle, on Thu Mar 09 11:41:06 2017, using Rez v2.7.0

    requested packages:
    sequence
    ~platform==linux   (implicit)
    ~arch==x86_64      (implicit)
    ~os==Ubuntu-16.04  (implicit)

    resolved packages:
    arch-x86_64      /sw/packages/arch/x86_64
    os-Ubuntu-16.04  /sw/packages/os/Ubuntu-16.04
    platform-linux   /sw/packages/platform/linux
    python-2.7.12    /sw/packages/python/2.7.12
    sequence-2.1.2   /home/ajohns/packages/sequence/2.1.2  (local)

Note here that the *sequence* package is a local install, denoted by the *(local)* label.
