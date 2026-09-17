===============
Getting started
===============

This guide takes you from a fresh Rez installation to building your own package
and running it inside a configured environment.

Before you begin
================

You need a working Rez installation. :doc:`installation` lists the supported
Python versions and covers the install itself.

.. important::
   Install Rez with the ``install.py`` script, not with ``pip install rez``. A
   pip installation provides the Rez API, but its command line tools are not
   guaranteed to work, and the commands in this guide assume a production
   install. See :ref:`why-not-pip-for-production`.

Confirm that Rez is available in your terminal:

.. code-block:: text

   ]$ rez-status

The examples below install packages into the :data:`local package path
<local_packages_path>`, which defaults to ``~/packages``. It is created when the
first package is installed.

Essential packages
==================

Rez models the current system as three packages: ``platform``, ``arch`` and
``os``. They are added to every resolve as
:ref:`implicit packages <implicit-packages-concept>`, so create them first.

The :ref:`rez-bind` tool creates Rez packages that reference software already
installed on your system. Binding ``os`` is enough, because ``os`` requires
``platform`` and ``arch``, and rez-bind creates a package's requirements
alongside it:

.. code-block:: text

   ]$ rez-bind os
   creating package 'os' in /home/you/packages...
   creating package 'platform' in /home/you/packages...
   creating package 'arch' in /home/you/packages...
   The following packages were installed:

   PACKAGE   URI
   -------   ---
   arch      /home/you/packages/arch/x86_64/package.py
   os        /home/you/packages/os/rocky-9/package.py
   platform  /home/you/packages/platform/linux/package.py

.. warning::
   :ref:`rez-bind` is going to be deprecated. The current implementation is not
   actively maintained, and most of its bind modules are likely to fail on
   Windows.

   Even though rez-bind will be deprecated and we generally discourage its use,
   you can safely use it to create the ``arch``, ``os`` and ``platform``
   packages.

These three packages describe *this* machine. Run ``rez-bind os`` separately on
every operating system and architecture that will use the package repository,
and do not copy the resulting packages between unlike platforms.

The ``os`` version is read from the running machine, so it can be more
fine-grained than you want to target. Windows reports a build number such as
``windows-10.0.19045``, and Linux distributions report point releases. Use
:data:`platform_map` to collapse these onto the versions you actually support,
before creating these packages for a shared repository.

A Python package
================

The example package below requires ``python``, so you need a ``python`` package
before you can build it. Bind the interpreter installed on your system:

.. code-block:: text

   ]$ rez-bind python

.. note::
   You may require administrative privileges for this.

Now you should be able to create an environment containing Python:

.. code-block:: text

   ]$ rez-env python -- python --version
   Python 3.9.16

A bound interpreter is a starting point, not a distribution strategy. It
references an installation that exists on one machine, so it cannot be shared
with a site-wide repository as-is.

There is no single blessed way to package Python for Rez yet. In practice sites
either build the interpreter from source as a normal Rez package, or repackage a
relocatable distribution. Whichever you choose, publish it with one
:doc:`variant <variants>` per supported platform so that a shared repository can
serve every machine, and see :doc:`building_packages` for wiring up the build
itself. Once a real ``python`` package exists, :ref:`rez-pip` can install
packages from PyPI against it, as described in :doc:`pip`.

Build your first package
========================

The Rez source contains a small example package in
``example_packages/hello_world``. Its ``package.py`` is short enough to read in
full:

.. literalinclude:: ../../example_packages/hello_world/package.py
   :language: python

It builds with a plain Python script, ``build.py``, which lives next to
``package.py`` and is run by :pkgdef:attr:`build_command`. That means this
example needs no build tooling beyond the ``python`` package you just created.

Use :ref:`rez-build` to build it and install it to your
:data:`local package path <local_packages_path>`:

.. code-block:: text

   ]$ cd example_packages/hello_world
   ]$ rez-build --install

See :doc:`building_packages` for how the build environment is constructed, how
to use CMake or another build system, and how to work in a local
build-install-test cycle.

Testing your package
====================

Use :ref:`rez-env` to request a configured environment containing your package:

.. code-block:: text

   ]$ rez-env hello_world

   You are now in a rez-configured environment.

   resolved by you@yourmachine, on Wed Sep 16 17:58:14 2026, using Rez v3.4.0

   requested packages:
   hello_world
   ~platform==linux  (implicit)
   ~arch==x86_64     (implicit)
   ~os==rocky-9      (implicit)

   resolved packages:
   arch-x86_64        /home/you/packages/arch/x86_64                                          (local)
   hello_world-1.0.0  /home/you/packages/hello_world/1.0.0                                    (local)
   os-rocky-9         /home/you/packages/os/rocky-9                                           (local)
   platform-linux     /home/you/packages/platform/linux                                       (local)
   python-3.9.16      /home/you/packages/python/3.9.16/platform-linux/arch-x86_64/os-rocky-9  (local)

   > ]$

The ``>`` prefix on your prompt means you are inside a Rez-configured subshell.
Every package is tagged ``(local)`` because they all came from your local
package path. Notice that ``python`` was resolved even though you only asked for
``hello_world``: Rez pulled it in because ``hello_world`` requires it, and it
added the three implicits automatically. See :doc:`basic_concepts` for how
resolving works, and :doc:`context` for what a resolved environment is made of.

.. note::
   The paths and prompts shown here are from Linux. On Windows the same resolve
   is written under ``%USERPROFILE%\packages``, and ``os`` will report a build
   number such as ``windows-10.0.19045``.

The ``hello_world`` package declares a :pkgdef:attr:`tools` entry, so its
``hello`` tool is on your ``PATH``:

.. code-block:: text

   > ]$ hello
   Hello world!

Leave the environment with the ``exit`` command or :kbd:`Control-D`.

You can also create a configured environment and run a single command inside it.
The shell exits as soon as the command finishes, which is the form you want in
scripts and automation:

.. code-block:: text

   ]$ rez-env hello_world -- hello
   Hello world!

Next steps
==========

* Read :doc:`configuring_rez`, and set :data:`packages_path` to the ordered list
  of repositories your users should search. Keep :data:`local_packages_path`
  writable so that local builds and development continue to work.
* Read :doc:`pip` to install packages from PyPI using :ref:`rez-pip`. Choose the
  target Python version explicitly, especially for packages that contain
  compiled extensions.
* Read :doc:`package_definition` for the full set of package attributes, and
  :doc:`package_commands` for what you can do in a ``commands()`` function.
* Read :doc:`variants` to publish a single package that supports several
  platforms, Python versions, or other combinations.
* Read :doc:`releasing_packages` when your packages are ready to be deployed to
  a shared repository rather than installed locally.
