# ![rez](media/rez_banner_256.png)

Rez is a cross-platform software package management API and set of tools. Rez can
build and install packages, and resolve environments at runtime using use a dependency
resolution algorithm to avoid version conflicts. Both third party and internally
developed packages can be made into Rez packages, and any kind of package (python,
compiled, etc) is supported.

The main tools are:

* **rez-env**: Creates a configured shell containing a set of requested packages.
  Supports *bash*, *tcsh* and *cmd* (Windows), and can be extended to other shells.

* **rez-build**: Builds a package of any type (python, C++ etc), and installs it
  locally for testing. Supports *cmake*, and can be extended to other build systems.

* **rez-release**: Builds and centrally deploys a package, and updates the associated
  source control repository (creating tags etc). Supports *git*, *mercurial*
  and *svn*, and can be extended to other repository types.

* **rez-gui**: A fully fledged graphical interface for creating resolved environments,
  launching tools and comparing different environments.

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
Because python is the language used to define a package's commands, behaviour is 
rich - a package can create aliases, source scripts and run commands, as well as 
manage environment variables; and all this combined with the program logic that 
python itself provides.

When an environment is created with the rez API or *rez-env* tool, a dependency
resolution algorithm tracks package requirements and resolves to a list of needed
packages. The commands from these packages are concatenated and evaluated, resulting
in a configured environment. Rez is able to configure environments containing 
hundreds of packages, often within a few seconds. Resolves can also be saved to file,
and when re-evaluated later will reconstruct the same environment once more.

## Examples

This example places the user into a resolved shell containing the requested packages:

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
    >>> print out
    '/software/ext/houdini/12.5.562/bin/hescape'


## Installation

To install Rez, download the source, and then from the source directory, run the
following command (replacing DEST_DIR with your preferred installation path):

    ]$ python ./install.py -v DEST_DIR

Please note that if this fails, there may be a problem with the python executable
you are using (it may be a custom python build). In this case try using
/usr/bin/python instead.

This installs the Rez command line tools. It will print a message at the end
telling you how to use Rez when the installation has completed. Rez is not a
normal Python package and so you do not typically install it with pip or setup.py.

To install the API, you have two options - you can either install it as a typical
Python package, or (and more usefully) you can install it as a Rez package itself.

To install Rez as a Rez package:

    ]$ rez-bind rez
    created package 'rez-2.0.0' in /home/ajohns/packages
    # Now we can resolve a rez environment, and use the API
    ]$ rez-env rez -- python -c 'import rez; print rez.__version__'
    2.0.0

To install Rez as a standard python module:

    ]$ pip install rez

Or, to install from source:

    ]$ python setup.py install


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
