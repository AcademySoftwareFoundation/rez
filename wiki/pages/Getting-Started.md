## Installation

First, install Rez. Download the source, and from the source directory, run
(with *DEST_DIR* replaced with your install location):

    ]$ python ./install.py -v DEST_DIR

This installs the Rez command line tools. It will print a message at the end
telling you how to use Rez when the installation has completed. Rez is not a
normal Python package and so you do not typically install it with pip or setup.py.
Do *not* move the installation - re-install to a new location if you want to
change the install path. If you want to install rez for multiple operating
systems, perform separate installs for each of those systems.

Next, you need to create some essential Rez packages. The *rez-bind* tool creates
Rez packages that reference software already installed on your system. Use the
*--quickstart* argument to bind a set of standard packages (note that you may
require administrative privileges for some of them):

    ]$ rez-bind --quickstart
    Binding platform into /home/ajohns/packages...
    Binding arch into /home/ajohns/packages...
    Binding os into /home/ajohns/packages...
    Binding python into /home/ajohns/packages...
    Binding rez into /home/ajohns/packages...
    Binding rezgui into /home/ajohns/packages...
    Binding setuptools into /home/ajohns/packages...
    Binding pip into /home/ajohns/packages...

    Successfully converted the following software found on the current system into Rez packages:

    PACKAGE     URI
    -------     ---
    arch        /home/ajohns/packages/arch/x86_64/package.py
    os          /home/ajohns/packages/os/osx-10.11.5/package.py
    pip         /home/ajohns/packages/pip/8.0.2/package.py
    platform    /home/ajohns/packages/platform/osx/package.py
    python      /home/ajohns/packages/python/2.7.11/package.py
    rez         /home/ajohns/packages/rez/2.0.rc1.44/package.py
    rezgui      /home/ajohns/packages/rezgui/2.0.rc1.44/package.py
    setuptools  /home/ajohns/packages/setuptools/19.4/package.py

Now you should be able to create an environment containing Python. Try this:

    ]$ rez-env python -- which python
    /home/ajohns/packages/python-2.7.8/platform-linux/arch-x86_64/os-Ubuntu-12.04/bin/python


## Building Your First Package

Before building your first rez package, ensure that:

* The directory *$HOME/packages* exists and is writable;
* The [cmake](https://cmake.org/) tool is available.

The *rez-build* tool is used to build packages and install them locally (typically
to *$HOME/packages*). Once you've done that, you can use them via *rez-env*, just
like any other package:

    ]$ cd example_packages/hello_world
    ]$ rez-build --install

    --------------------------------------------------------------------------------
    Building hello_world-1.0.0...
    --------------------------------------------------------------------------------
    Resolving build environment: python
    resolved by ajohns@workstation.local, on Sun Jul 31 14:39:33 2016, using Rez v2.0.rc1.44

    requested packages:
    python
    ~platform==osx    (implicit)
    ~arch==x86_64     (implicit)
    ~os==osx-10.11.5  (implicit)

    resolved packages:
    arch-x86_64     /home/ajohns/packages/arch/x86_64                                            (local)
    os-osx-10.11.5  /home/ajohns/packages/os/osx-10.11.5                                         (local)
    platform-osx    /home/ajohns/packages/platform/osx                                           (local)
    python-2.7.11   /home/ajohns/packages/python/2.7.11/platform-osx/arch-x86_64/os-osx-10.11.5  (local)

    Invoking cmake build system...
    Executing: /usr/local/bin/cmake -d /home/ajohns/workspace/rez/example_packages/hello_world -Wno-dev -DCMAKE_ECLIPSE_GENERATE_SOURCE_PROJECT=TRUE -D_ECLIPSE_VERSION=4.3 --no-warn-unused-cli -DCMAKE_INSTALL_PREFIX=/home/ajohns/packages/hello_world/1.0.0 -DCMAKE_MODULE_PATH=${CMAKE_MODULE_PATH} -DCMAKE_BUILD_TYPE=Release -DREZ_BUILD_TYPE=local -DREZ_BUILD_INSTALL=1 -G Unix Makefiles
    Not searching for unused variables given on the command line.
    -- Could NOT find PkgConfig (missing:  PKG_CONFIG_EXECUTABLE)
    -- Configuring done
    -- Generating done
    -- Build files have been written to: /home/ajohns/workspace/rez/example_packages/hello_world/build

    Executing: make -j4
    [100%] Built target py

    Executing: make -j4 install
    [100%] Built target py
    Install the project...
    -- Install configuration: "Release"
    -- Installing: /home/ajohns/packages/hello_world/1.0.0/./python/hello_world.py
    -- Installing: /home/ajohns/packages/hello_world/1.0.0/./python/hello_world.pyc
    -- Installing: /home/ajohns/packages/hello_world/1.0.0/./bin/hello

    All 1 build(s) were successful.

You have just built your first package, and installed it to the *local package path*, which defaults
to (and is usually kept as) *$HOME/packages*.


## Testing Your Package

You can use the *rez-env* tool to request a configured environment containing your package:

    ]$ rez-env hello_world

    You are now in a rez-configured environment.

    resolved by ajohns@workstation.local, on Sun Jul 31 14:43:54 2016, using Rez v2.0.rc1.44

    requested packages:
    hello_world
    ~platform==osx    (implicit)
    ~arch==x86_64     (implicit)
    ~os==osx-10.11.5  (implicit)

    resolved packages:
    arch-x86_64        /home/ajohns/packages/arch/x86_64                                            (local)
    hello_world-1.0.0  /home/ajohns/packages/hello_world/1.0.0                                      (local)
    os-osx-10.11.5     /home/ajohns/packages/os/osx-10.11.5                                         (local)
    platform-osx       /home/ajohns/packages/platform/osx                                           (local)
    python-2.7.11      /home/ajohns/packages/python/2.7.11/platform-osx/arch-x86_64/os-osx-10.11.5  (local)

    > ]$ █

Now you are within the configured environment. The caret (>) prefixed to your prompt is a visual cue
telling you that you're within a rez-configured subshell. Rez does not update the currect environment,
instead it configures a subshell and puts you within it.

Now you can run the *hello* tool in our *hello_world* package:

    > ]$ hello
    Hello world!

If you're within a rez shell, and you forget what packages are currently available or want to see the
list again, you can use the *rez-context* tool. It prints the same information you see when you
initially created the environment:

    > ]$ rez-context
    resolved by ajohns@workstation.local, on Sun Jul 31 14:43:54 2016, using Rez v2.0.rc1.44

    requested packages:
    hello_world
    ~platform==osx    (implicit)
    ~arch==x86_64     (implicit)
    ~os==osx-10.11.5  (implicit)

    resolved packages:
    arch-x86_64        /home/ajohns/packages/arch/x86_64                                            (local)
    hello_world-1.0.0  /home/ajohns/packages/hello_world/1.0.0                                      (local)
    os-osx-10.11.5     /home/ajohns/packages/os/osx-10.11.5                                         (local)
    platform-osx       /home/ajohns/packages/platform/osx                                           (local)
    python-2.7.11      /home/ajohns/packages/python/2.7.11/platform-osx/arch-x86_64/os-osx-10.11.5  (local)

To exit the configured environment, simply exist the shell using the *exit* command:

    > ]$ exit
    ]$ █

You can also create a configured environment and run a command inside of it, with a single command.
When you use this form, the shell is immediately exited after the command runs:

    ]$ rez-env hello_world -- hello
    Hello world!
    ]$ █
