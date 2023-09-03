===
Pip
===

Rez is language agnostic.
But since python is so much used in the VFX industry (and outside),
it knows how to convert/translate it into a rez package.
To do so, it provides a :ref:`rez-pip` command.

.. warning::
   It doesn't know how to translate its own packages into pip packages.

.. hint::
   We are planning to introduce a new rez-pip implemented as a plugin that will
   overcome most of the current rez-pip limitations and annoyances.

Usage
=====

.. code-block:: text

   usage: rez pip [-h] [--python-version VERSION] [--pip-version VERSION] [-i]
                  [-s] [-r] [-v]
                  PACKAGE

   Install a pip-compatible python package, and its dependencies, as rez
   packages.

   positional arguments:
   PACKAGE               package to install or archive/url to install from

   optional arguments:
   -h, --help            show this help message and exit
   --python-version VERSION
                           python version (rez package) to use, default is
                           latest. Note that the pip package(s) will be installed
                           with a dependency on python-MAJOR.MINOR.
   --pip-version VERSION
                           pip version (rez package) to use, default is latest.
                           This option is deprecated and will be removed in the
                           future.
   -i, --install         install the package
   -s, --search          search for the package on PyPi
   -r, --release         install as released package; if not set, package is
                           installed locally only
   -p PATH, --prefix PATH
                           install to a custom package repository path.
   -v, --verbose         verbose mode, repeat for more verbosity


The :ref:`rez-pip` command allows you to do two main things.

1. Install or release a pip package as a rez package.
2. Search for a package on PyPI

.. _which-pip-will-be-used:

Which pip will be used?
=======================

:ref:`rez-pip` uses a fallback mechanism to find which pip will be used to run the commands.
The logic is as follow:

1. Search for pip in the rezified ``python`` package specified with :option:`--python-version <rez-pip --python-version>`, or
   the latest version if not specified;
2. If found, use it;
3. If not found, search for pip in the rezified ``pip`` package specified with :option:`--pip-version <rez-pip --pip-version>`,
   or latest version if not specified.

   .. note::
      Note that this is deprecated and will be removed in the future

4. If rezified ``pip`` is found, use it;
5. If not found, fall back to pip installed in rez own virtualenv.

.. note::
   In all of these options, we also check if the version of pip is greater or equal
   than 19.0. This is a hard requirement of :ref:`rez-pip`.

Note that rez-pip output should tell you what it tries and which pip it will use.

It is extremely important to know which pip is used and understand why it is used. Pip packages
define which python version they are compatible with.
When you install a pip package, pip checks which python version it is
currently running under to determine if a package can be downloaded and installed.
Not only this but it also checks which python implementation is used (CPython, PyPy,
IronPython, etc), the architecture python was built with, and other variables. So the thing you
really need to know first is which python you want to use and from there you should know
which pip is used. Knowing the pip version comes in second place.

At some point, we supported the :option:`--pip-version <rez-pip --pip-version>` argument, but considering what was just said
above, we decided to deprecate it (but not yet removed) just for backward compatibility reasons.
Pip is too much (read tightly) coupled to the python version/interpreter it is installed with
for us to support having pip as a rez package. We just can't guarantee that pip can be
install once in a central way and work with multiple different python version, and potentially
different implementations.

.. _how-should-i-install-pip:

How should I install pip?
=========================

Following the :ref:`which-pip-will-be-used` section, we recommend to install
pip inside your python packages. For Python 2, this can be done when you compile it with the
``--with-ensurepip`` flag of the ``configure`` script. This will install a version older than 19.0
though, so you will need to upgrade it. For Python 3, it is already installed by default.
Though your mileage may vary for the version installed, depending on which Python version you
installed. So check the pip version and update it if necessary. We also encourage you
to install ``wheel`` and possibly update ``setuptools``. ``pip``, ``setuptools`` and ``wheel``
are perfectly fine when installed in the interpreter directly as they are pretty core
packages and all have no dependencies (and that's what ``virtualenv`` does by default too).

.. tip::
   When installing something in an interpreter, make sure you really install in this interpreter.
   That means using something like:

   .. code-block:: console

      $ /path/to/python -E -s -m pip install <package>

   ``-E`` will render any ``PYTHON*`` environment variable to not be used and ``-s`` will
   remove your :mod:`user site <site>` from the equation.

Install/release
---------------

You have two options when you want to convert a pip package to a rez package. You can
install it, or release it. Install means that it will install in your
:data:`local_packages_path`, while
release means it will be installed in your :data:`release_packages_path`.
You can also specify a custom installation location using :option:`--prefix <rez-pip --prefix>` (or ``-p``).

You can (and we recommend) use :option:`--python-version <rez-pip --python-version>` to choose for which python
version you want to install a given package. This will make ``rez-pip`` to resolve
the given version of the ``python`` rez package and use it to run the ``pip install``.
See :ref:`which-pip-will-be-used` for more details.
If the pip package is not pure (so contains ``.so`` for example), you will need to
call :ref:`rez-pip` for each python version you want to install the pip package for.

.. warning::
   :option:`--pip-version <rez-pip --pip-version>` is deprecated and will be removed in the future.
   See :ref:`how-should-i-install-pip` on how we recommend
   to install pip from now on.
