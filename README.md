[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/AcademySoftwareFoundation/rez/blob/main/LICENSE)<br>
[![Release](https://shields.io/github/v/release/AcademySoftwareFoundation/rez)](https://github.com/AcademySoftwareFoundation/rez/releases)
[![PyPI Release](https://shields.io/pypi/v/rez)](https://pypi.org/project/rez)<br>
[![Mailing List](https://img.shields.io/badge/rez--discussion-lists.aswf.io-003366?style=flat-square&logo=linuxfoundation)](https://lists.aswf.io/g/rez-discussion)
[![Slack](https://img.shields.io/badge/Slack-ASWF_%23rez-7a6800?style=flat-square&logo=slack)](https://slack.aswf.io/)
[![Contributing Guidelines](https://img.shields.io/badge/rez-Contributing%20Guidelines-0b610e?style=flat-square&logo=github)](https://github.com/AcademySoftwareFoundation/rez/blob/main/CONTRIBUTING.md)<br>
[![Tests](https://github.com/AcademySoftwareFoundation/rez/actions/workflows/tests.yaml/badge.svg)](https://github.com/AcademySoftwareFoundation/rez/actions/workflows/tests.yaml)
[![Installation](https://github.com/AcademySoftwareFoundation/rez/actions/workflows/installation.yaml/badge.svg)](https://github.com/AcademySoftwareFoundation/rez/actions/workflows/installation.yaml)
[![Flake8](https://github.com/AcademySoftwareFoundation/rez/actions/workflows/flake8.yaml/badge.svg)](https://github.com/AcademySoftwareFoundation/rez/actions/workflows/flake8.yaml)
[![Docs](https://readthedocs.org/projects/rez/badge/?version=stable)](https://rez.readthedocs.io/en/stable)
[![PyPI](https://github.com/AcademySoftwareFoundation/rez/workflows/pypi/badge.svg)](https://github.com/AcademySoftwareFoundation/rez/actions?query=workflow%3Apypi+event%3Arelease)
[![Benchmark](https://github.com/AcademySoftwareFoundation/rez/workflows/benchmark/badge.svg)](https://github.com/AcademySoftwareFoundation/rez/actions?query=workflow%3Abenchmark+event%3Arelease)<br>
[![Coverage](https://codecov.io/gh/AcademySoftwareFoundation/rez/graph/badge.svg?token=FLYggQOE7W)](https://codecov.io/gh/AcademySoftwareFoundation/rez)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=AcademySoftwareFoundation_rez&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=AcademySoftwareFoundation_rez)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=AcademySoftwareFoundation_rez&metric=bugs)](https://sonarcloud.io/summary/new_code?id=AcademySoftwareFoundation_rez)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=AcademySoftwareFoundation_rez&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=AcademySoftwareFoundation_rez)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=AcademySoftwareFoundation_rez&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=AcademySoftwareFoundation_rez)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=AcademySoftwareFoundation_rez&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=AcademySoftwareFoundation_rez)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=AcademySoftwareFoundation_rez&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=AcademySoftwareFoundation_rez)


- [What Is Rez?](#what-is-rez)
- [The Basics](#the-basics)
- [Examples](#examples)
- [Quickstart](#quickstart)
- [Building Your First Package](#building-your-first-package)
- [Features](#features)


## What Is Rez?

Rez is a cross-platform package manager with a difference. Using Rez you can create
standalone environments configured for a given set of packages. However, unlike many
other package managers, packages are not installed into these standalone environments.
Instead, all package versions are installed into a central repository, and standalone
environments reference these existing packages. This means that configured environments
are lightweight, and very fast to create, often taking just a few seconds to configure
despite containing hundreds of packages.

See [the wiki](https://rez.readthedocs.io) for full documentation.

<p align="center">
<a href="https://github.com/AcademySoftwareFoundation/rez/raw/main/docs/source/_static/other_pkg_mgr.png">
<img src="https://github.com/AcademySoftwareFoundation/rez/raw/main/docs/source/_static/other_pkg_mgr.png"></a>
<br><i>Typical package managers install packages into an environment</i>
</p>

<br>
<p align="center">
<a href="https://github.com/AcademySoftwareFoundation/rez/raw/main/docs/source/_static/rez_pkg_mgr.png">
<img src="https://github.com/AcademySoftwareFoundation/rez/raw/main/docs/source/_static/rez_pkg_mgr.png"></a>
<br><i>Rez installs packages once, and configures environments dynamically</i>
</p>

<br>
Rez takes a list of package requests, and constructs the target environment, resolving
all the necessary package dependencies. Any type of software package is supported -
compiled, python, applications and libraries.


## The Basics

Packages are stored in repositories on disk. Each package has a single concise
definition file (*package.py*) that defines its dependencies, its commands (how it
configures the environment containing it), and other metadata. For example, the
following is the package definition file for the popular *requests* python module:

    name = "requests"

    version = "2.8.1"

    authors = ["Kenneth Reitz"]

    requires = [
        "python-2.7+"
    ]

    def commands():
        env.PYTHONPATH.append("{root}/python")

This package requires python-2.7 or greater. When used, the 'python' subdirectory
within its install location is appended to the PYTHONPATH environment variable.

When an environment is created with the rez API or *rez-env* tool, a dependency
resolution algorithm tracks package requirements and resolves to a list of needed
packages. The commands from these packages are concatenated and evaluated, resulting
in a configured environment. Rez is able to configure environments containing
hundreds of packages, often within a few seconds. Resolves can also be saved to file,
and when re-evaluated later will reconstruct the same environment once more.


## Examples

This example places the user into a resolved shell containing the requested packages,
using the [rez-env](https://rez.readthedocs.io/en/stable/commands/rez-env.html) tool:

    ]$ rez-env requests-2.2+ python-2.6 'pymongo-0+<2.7'

    You are now in a rez-configured environment.

    resolved by ajohns@nn188.somewhere.com, on Wed Feb 26 15:56:20 2014, using Rez v2.0.0

    requested packages:
    requests-2.2+
    python-2.6
    pymongo-0+<2.7

    resolved packages:
    python-2.6.8    /software/ext/python/2.6.8
    platform-linux  /software/ext/platform/linux
    requests-2.2.1  /software/ext/requests/2.2.1/python-2.6
    pymongo-2.6.3   /software/ext/pymongo/2.6.3
    arch-x86_64     /software/ext/arch/x86_64

    > ]$ _

This example creates an environment containing the package 'houdini' version 12.5
or greater, and runs the command 'hescape -h' inside that environment:

    ]$ rez-env houdini-12.5+ -- hescape -h
    Usage: hescape [-foreground] [-s editor] [filename ...]
    -h: output this usage message
    -s: specify starting desktop by name
    -foreground: starts process in foreground

Resolved environments can also be created via the API:

    >>> import subprocess
    >>> from rez.resolved_context import ResolvedContext
    >>>
    >>> r = ResolvedContext(["houdini-12.5+", "houdini-0+<13", "java", "!java-1.8+"])
    >>> p = r.execute_shell(command='which hescape', stdout=subprocess.PIPE)
    >>> out, err = p.communicate()
    >>>
    >>> print(out)
    '/software/ext/houdini/12.5.562/bin/hescape'


## Quickstart

First, install Rez using Python 3.7+. Download the source, and from the source directory, run
(with DEST_DIR replaced with your install location):

    ]$ python3 ./install.py -v DEST_DIR

This installs the Rez command line tools. It will print a message at the end
telling you how to use Rez when the installation has completed. Rez is not a
normal Python package and so you do not typically install it with pip or setup.py.
Do *not* move the installation - re-install to a new location if you want to
change the install path. If you want to install rez for multiple operating
systems, perform separate installs for each of those systems.

Next, you need to create some essential Rez packages. The *rez-bind* tool creates
Rez packages that are based on software already installed on your system. Try
binding the following list of packages (note that for Python, you may need
administrative privileges):

    ]$ rez-bind platform
    ]$ rez-bind arch
    ]$ rez-bind os
    ]$ rez-bind python

Now you should be able to create an environment containing Python. Try this:

    ]$ rez-env python -- which python
    /home/ajohns/packages/python-2.7.8/platform-linux/arch-x86_64/os-Ubuntu-12.04/bin/python


## Building Your First Package

The *rez-build* tool is used to build packages and install them locally (typically
to *$HOME/packages*). Once you've done that, you can use them via *rez-env*, just
like any other package:

    ]$ cd example_packages/hello_world
    ]$ rez-build --install
    ...
    ]$ rez-env hello_world -- hello
    Hello world!


## Features

* Supports Linux, OSX and Windows;
* Allows for a fast and efficient build-install-test cycle;
* Creates shells of type: bash, tcsh, other (shells can be added as plugins);
* Contains a deployment system supporting git, mercurial and svn (as plugins);
* Environment resolves can be saved to disk and reused at a later date (a bit
  like VirtualEnv);
* Highly pluggable, supports five different plugin types to do things from
  adding new shell types, to adding new build systems;
* Contains a version resolving algorithm, for avoiding version clashes;
* Visualises resolved environments in a rendered dot-graph;
* Packages are found in a search path, so different packages can be deployed
  to different locations;
* Supports alphanumeric version numbers;
* Has a powerful version requirements syntax, able to describe any version
  range, and a conflict operator for rejecting version ranges;
* Package 'variants' - a way to define different flavors of the same package
  version, for example a plugin built for multiple versions of the host app;
* Custom release hooks (such as post-release operations) can be added as plugins;
* Has a time lock feature, which allows old resolves to be recreated (newer
  packages are ignored);
* Package definitions are a single, succinct file;
* Packages define their effect on the environment (adding to PATH etc) in a
  platform- and shell- agnostic way, using a dedicated python API;
* Has a memcached-based caching system, for caching environment resolves;
* Has a package filtering feature, allowing for staged package releases such as
  alpha and beta packages.

## You have a problem or want to talk to us?

If you find a bug, need help, or want to talk to the developers, here is a list of the different
ways to get in touch with us:

* [Report an issue](https://github.com/AcademySoftwareFoundation/rez/issues)
* [Chat room](https://slack.aswf.io): Join the ``#rez`` channel
* [Start a discussion](https://github.com/AcademySoftwareFoundation/rez/discussions)
* [Mailing list](mail:main@lists.aswf.io): Note that are way less active on the mailing
  list than on any other communication channel.

## Known issues and limitations

* Currently CMake builds do not function on Windows with Rez and
  the related tests are skipped. A fix requires multiple changes that are on
  the roadmap. Users have successfully implemented workarounds to utilize
  CMake with Rez under Windows, but the goal is to provide a seamless experience
  on any platform in the future. For details see this [issue](/../../issues/703)
