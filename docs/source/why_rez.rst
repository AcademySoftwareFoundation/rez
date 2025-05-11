=======
Why Rez
=======

What is Rez
===========

Rez v1 was originally built in 2011 by Allan Johns and was open-sourced in 2013.

It was with VFX/Animation workflows in mind, where different productions can have non-homogenous package
requests and shared filesystems are the norm.

Rez is both a package manager and an environment manager.

Package Manager
---------------

A package manager is a tool that helps keep track of an application's dependencies. Package managers provide
often communicate with package repositories to install, update and remove packages on a computer.


Environment Manager
-------------------

A runtime environment manager is a tool that allows users to easily control what a shell created environment
will look like. This primarily takes shape by defining environment variables that will then be used by
applications that are launched from the created shell.


What Rez is not
===============
Rez is not a configuration system. It does not and should not have any knowledge as to the content of a user's
package requests.

In VFX/Animation for example, a common problem is that different projects or "shows" may need to use different
versions of software/tools. This is especially problematic with long-standing productions such as feature films.

Let's say there are two shows in production, show1 that should use Autodesk Maya 2018, and show2 that should use
Maya 2019. The mechanism that stores and retrieves this configuration information is the configuration system.

This configuration could commonly be stored in a database, and it would be tedious and error-prone to force
non-technical artists to lookup this information and write Rez requests themselves.

For this reason, it's common that the more technical folks of the studio would want to build a CLI or GUI "launcher"
to expose to the less technical artists of the studio that would allow them to select which project they are working
on, and perhaps which DCC tool they want to use, and the launcher will automatically formulate the Rez request.

For example, a hypothetical CLI launcher like so:

.. code-block:: console

    usage: studio_launcher.py [-h] [-p PROJECT] dcc

    A simple CLI launcher.

    positional arguments:
      dcc                       DCC tool to launch

    options:
      -h, --help                show this help message and exit
      -p, --project PROJECT     The name of the project

This launcher would know to communicate with the configuration system in order to lookup which version of the DCC
to use and would also request any other packages that are needed (such as proprietary workflow tools).

Alternatives to Rez
===================

Package Managers
----------------

`pip <https://packaging.python.org/en/latest/key_projects/#pip>`_

Environment Managers
--------------------
`venv <https://packaging.python.org/en/latest/key_projects/#venv>`_

`virtualenv <https://packaging.python.org/en/latest/key_projects/#virtualenv>`_

Package and Environment Managers
--------------------------------
`conda <https://packaging.python.org/en/latest/key_projects/#conda>`_

Conda was primarily created to solve packaging problems in the Python ecosystem, but is not Python specific.
Conda creates persistent, on-disk environments while Rez creates in-memory ephemeral environments. Rez doesn't
have to local install packages to work (but it can with the package caching feature), where Conda does.

This feature of Rez is very useful is VFX/Animation where "work" is done on render farm machines whose disk space is
often quite limited. Shared filesystems are common in VFX/Animation, which means they are often configured to be
accessed very quickly. Due to this, Rez is very fast.

Conda *can* create environments on shared filesystems, but
there would be lots of caveats and hidden dragons.

`spack <https://packaging.python.org/en/latest/key_projects/#spack>`_

`Conan <https://docs.conan.io/2/>`_

`SPK <https://getspk.io/>`_


