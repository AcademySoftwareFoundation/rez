## Introduction

Rez is a cross-platform, LGPL Licensed python library and set of utilities for
building and installing packages, and resolving environments containing these
packages at runtime, avoiding version conflicts. The main tools are:

* **rez-env** - Creates a configured shell containing a set of requested packages.
  Supports **bash** and **tcsh**, and mimics the startup sequences of the native shell.

* **rez-build** - Builds a package of any type (python, C++ etc), and installs it
  locally for testing. Supports **cmake**.

* **rez-release** - Builds and centrally deploys a package, and updates the associated
  source control repository (creating tags etc). Supports **git**, **mercurial**
  and **svn**.

Unlike many packaging systems, Rez is able to install many different versions of
the same packages. When you use the rez-env tool, a new environment is dynamically
created, containing the requested packages. Rez resolves environments at runtime,
rather than install time - however, you are able to store a resolve to disk, and
reuse it at a later date.

Here's an example which places the user into a resolved shell containing the
requested packages:

    ]$ rez-env requests-2.2+ python-2.6 'pymongo-0+<2.7'

    You are now in a rez-configured environment.

    resolved by ajohns@nn188.somewhere.com, on Wed Feb 26 15:56:20 2014, using Rez v2.0.0

    implicit packages:
    platform-linux
    arch-x86_64

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

Here's an example which creates an environment containing the package 'houdini'
version 12.5 or greater, and runs the command 'hescape -h' inside that environment:

    ]$ rez-env -c 'hescape -h' houdini-12.5+
    Usage: hescape [-foreground] [-s editor] [filename ...]
    -h: output this usage message
    -f: force the use of asset definitions in OTL files on the command line
    -s: specify starting desktop by name
    -foreground: starts process in foreground

Resolved environments can also be created programmatically:

    >>> from rez.resolved_context import ResolvedContext
    >>>
    >>> r = ResolvedContext(["houdini-12.5+", "houdini-0+<13", "java", "!java-1.8+"])
    >>>
    >>> r.print_info()
    resolved by ajohns@nn188.somewhere.com, on Wed Feb 26 13:03:30 2014, using Rez v2.0.0

    implicit packages:
    platform-linux
    arch-x86_64

    requested packages:
    houdini-12.5+
    houdini-0+<13
    java

    resolved packages:
    java-1.7.21       /software/ext/java/1.7.21
    platform-linux    /software/ext/platform/linux
    arch-x86_64       /software/ext/arch/x86_64
    houdini-12.5.562  /software/ext/houdini/12.5.562
    >>>
    >>> import subprocess
    >>> p = r.execute_shell(command='which hescape', stdout=subprocess.PIPE)
    >>> stdout,stderr = p.communicate()
    >>>
    >>> print stdout
    '/software/ext/houdini/12.5.562/bin/hescape'


## Features

* Supports Linux and OSX;
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
* Has a memcached-based caching system, for caching environment resolves.


## Installation

To install Rez, simply:

    pip install rez

Or, to install from source:

    python setup.py install

To see that it's working:

    ]$ rez-env -c 'hello_world' hello_world
    Hello Rez World!

## Documentation

TODO
