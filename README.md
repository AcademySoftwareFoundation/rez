Rez is a cross-platform, GPL-licensed python library and set of utilities for
building and installing packages, and resolving environments containing these
packages at runtime, avoiding version conflicts. The main tools are:

* **rez-env** - Creates a configured shell containing a set of requested packages.
  Supports **bash** and **tcsh**, and mimicks the startup sequences of the native shell.

* **rez-build** - Builds a package of any type (python, C++ etc), and installs it
  locally for testing. Supports **cmake**.

* **rez-release** - Builds and centrally deploys a package, and updates the associated
  source control repository accordingly (creating tags etc). Supports **git**,
  **mercurial** and **svn**.

Unlike many packaging systems, Rez is able to install many different versions of
the same packages. When you use the rez-env tool, a new environment is dynamically
created, containing the requested packages.

Here's an example which creates an environment containing the package 'houdini'
version 12.5 or greater, and runs the command '_hescape -h_' inside that environment:

    ]$ rez-env -c 'hescape -h' houdini-12.5+
    Usage: hescape [-foreground] [-s editor] [filename ...]
    -h: output this usage message
    -f: force the use of asset definitions in OTL files on the command line
    -s: specify starting desktop by name
    -foreground: starts process in foreground

Resolved environments can also be created programatically:

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
* Creates shells of type: bash, tcsh, other (shells can be added as plugins);
* Supports git, mercurial and svn;
* Contains a version resolving algorithm, for avoiding version clashes;
* Visualises resolved environments in a rendered dot-graph;
* Supports alphanumeric version numbers;
* Package 'variants' - a way to define different flavors of the same package
  version, for example a plugin built for multiple versions of the host app;
* Package definitions are a single, succinct file;
* Packages define their effect on the environment (adding to PATH etc) in a
  platform- and shell- agnostic way, using a dedicated python API;
* Supports a memcached-based caching system, for caching environment resolves.
