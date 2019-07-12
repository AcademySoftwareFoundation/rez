# Installation

See https://github.com/nerdvegas/rez/wiki/Getting-Started#installation


First, install Rez. Download the source, and, from the source directory, run:

```
]$ python ./install.py
```

This installs rez to `/opt/rez`. See `install.py -h` for how to install to a
different location.

Once the installation is complete, a message tells you how to run it:

```
SUCCESS! To activate Rez, add the following path to $PATH:
/opt/rez/bin/rez

You may also want to source the completion script (for bash):
source /opt/rez/completion/complete.sh
```

Do _not_ move the installation - re-install to a new location if you want to
change the install path. If you want to install rez for multiple operating
systems, perform separate installs for each of those systems.


# Installation Via Pip

It is possible to install rez with pip, like so:

```
]$ pip install rez
```

However, this comes with a caveat - _rez command line tools are disabled once
inside a rez environment (ie after using the `rez-env` command)_. The reasons
are given in the next section.

Rez installation via pip is not considered production ready. However, if all you
want is the rez API, and you don't need its tools to be available within rez
environments, then you can install with pip.


# Why Not Pip For Production?

Rez is not a normal python package. Although it can successfully be installed
using standard mechanisms such as pip, this comes with a number of caveats.
Specifically:

* When within a rez environment (ie after using the `rez-env` command), the rez
  command line tools would not be guaranteed to function correctly;
* When within a rez environment, other packages' tools (that were also installed
  with pip) would remain visible, but would not be guaranteed to work.

When you enter a rez environment, the rez packages in the resolve configure
that environment as they see fit. For example, it is not uncommon for a python
package to append to PYTHONPATH. Environment variables such as PYTHONPATH
affect the behaviour of tools, including rez itself, and this can cause it to
crash or behave abnormally.

When you use the `install.py` script to install rez, some extra steps are taken
to avoid this problem. Specifically:

* Rez is installed into a virtualenv so that it operates standalone;
* The rez tools are shebanged with `python -E`, in order to protect them from
  environment variables that affect python's behaviour;
* The rez tools are stored in their own directory, so that other unrelated tools
  are not visible.

Due to the way standard wheel-based python installations work, it simply is not
possible to perform these extra steps without using a custom installation script.
Wheels do not give the opportunity to run post-installation code; neither do
they provide functionality for specifying interpreter arguments to be added for
any given entry point.

It is possible to get around these issues to some extent, but doing so would
introduce a second code path parallel to the `install.py` -based installation,
and more caveats are introduced. For example, rez tools could detect when they're
run from a non-production installation, and could remove those parts of `sys.path`
that have come from PYTHONPATH. However, this doesn't take into account other
environment variables (such as PYTHONHOME). Neither does it solve the problem of
other unrelated tools remaining visible within the rez environment (and thus
potentially crashing or behaving abnormally).
