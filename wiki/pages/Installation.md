## Installation Script

To install rez, download the source. Then from the root directory, run:

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

> [[media/icons/warning.png]] Do _not_ move the installation - re-install to a new
> location if you want to change the install path. If you want to install rez for
> multiple operating systems, perform separate installs for each of those systems.


## Installation Via Pip

It is possible to install rez with pip, like so (from source root directory):

```
]$ pip install --target /opt/rez .
```

The `.` (dot) can also be replaced with link to the GitHub repository, 
e.g. choose from:

  - `git+https://github.com/nerdvegas/rez.git` if you have git installed
  - `https://github.com/nerdvegas/rez/archive/master.zip`
  - `https://github.com/nerdvegas/rez/archive/master.tar.gz`

> [[media/icons/warning.png]] The [PyPi rez](https://pypi.org/project/rez) is 
> not up to date as of writing. Avoid `pip install rez`

The environment variables to activate `rez` will be slightly different:

1. Add `/opt/rez` to `PYTHONPATH` for API e.g. `python -c 'import rez`
2. Add `/opt/rez/bin` to `PATH` for CLI, e.g. `rez-env`
  > [[media/icons/warning.png]] For these pip based installs, rez command line
  > tools **are not guaranteed to work correctly** inside a rez environment,
  > i.e. `rez-env` then running `rez-context` inside sub-shell.
  >
  > See [Why Not Pip For Production?](#why-not-pip-for-production) below.
  > You will also be warned with the following message in the terminal:
  > ```
  > Pip-based rez installation detected. Please be aware that rez command line
  > tools are not guaranteed to function correctly in this case. See
  > https://github.com/nerdvegas/rez/wiki/Installation#why-not-pip-for-production
  > for further details.
  > ```

Alternatively, if you already have `rez` setup and have `pip>=19` available,
you can then install `rez` as a `rez` package by using:

    ]$ rez-pip --install .

Pip installation is adequate however, if all you require is the rez API, or you
don't require its command line tools (`rez-context`, `rez-search`, `rez-view`,
etc) to be available within a resolved environment.

### Why Not Pip For Production?

Rez is not a normal python package. Although it can successfully be installed
using standard mechanisms such as pip, this comes with a number of caveats.
Specifically:

* When within a rez environment (ie after using the `rez-env` command), the rez
  command line tools are not guaranteed to function correctly;
* When within a rez environment, other packages' tools (that were also installed
  with pip) remain visible, but are not guaranteed to work.

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
