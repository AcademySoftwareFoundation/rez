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

