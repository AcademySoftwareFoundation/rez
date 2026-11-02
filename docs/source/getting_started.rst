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
   Rez must be installed via the install script to function correctly. See
   :ref:`why-not-pip-for-production`.

Confirm that Rez is available in your terminal:

.. code-block:: text

   ]$ rez-status

The examples below install packages into the :data:`local package path
<local_packages_path>`, which defaults to ``~/packages``. It is created when the
first package is installed.

Essential packages
==================

Rez models the current system as three packages: ``platform``, ``arch`` and
``os``. By default, they are added to every solve via
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
   :ref:`rez-bind` is deprecated. The current implementation is not
   actively maintained, and most of its bind modules are likely to fail on
   Windows.

   Even though rez-bind is deprecated and its usage is discouraged,
   you can safely use it to create the ``arch``, ``os`` and ``platform``
   packages.

These three packages describe *this* machine. Run ``rez-bind os`` separately on
every operating system and architecture where you wish to use rez.

Build your first package
========================

Create a directory containing a file named ``package.py``:

.. code-block:: python

   name = "hello_world"

   version = "1.0.0"

   description = "This is your first package"

   build_command = False

   def commands():
       alias("hello-world", "echo 'Hello, World!'")

Don't worry too much about the details for now. Use :ref:`rez-build` to build it
and install it:

.. code-block:: text

   ]$ rez-build --install

Testing your package
====================

Use :ref:`rez-env` to create an environment containing your package:

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

   > ]$

The ``>`` prefix on your prompt means you are inside a rez environment.
Every package is tagged ``(local)`` because they all came from your local
package path. Rez added the three implicit packages automatically. See
:doc:`basic_concepts` for how resolving works, and :doc:`context` for what a
resolved environment is made of.

.. note::
   The paths and prompts shown here are from Linux. On Windows the same resolve
   is written under ``%USERPROFILE%\packages``, and ``os`` will report a build
   number such as ``windows-10.0.19045``.

The ``hello_world`` package defines a ``hello-world`` alias, so you can run it:

.. code-block:: text

   > ]$ hello-world
   Hello, World!

To exit the configured environment, exit the shell using the ``exit`` command or
:kbd:`Control-d`.

You can also create a configured environment and run a single command inside it.
The shell exits as soon as the command finishes, which is the form you want in
scripts and automation:

.. code-block:: text

   ]$ rez-env hello_world -- hello-world
   Hello, World!
   ]$

Notice that the prompt has no ``>`` prefix: you are back outside of a rez
environment.

Next steps
==========

* Read :doc:`basic_concepts` to learn more about the core concepts of rez.
* Read :doc:`releasing_packages` to learn how to release your packages.
* Read :doc:`building_packages` to learn more about how to build a package.
* Read :doc:`pip` to learn how to make PyPI packages available as rez packages.

Targeting fewer operating system versions
-----------------------------------------

The ``os`` version is read from the running machine, so it can be more
fine-grained than you want to target. Windows reports a build number such as
``windows-10.0.19045``, and Linux distributions report versions such as
``rocky-9.4``. Use the :data:`platform_map` setting to collapse these onto the
versions you actually support, before creating these packages for a shared
repository.
