========
Security
========

.. important::
   This page is a work in progress.

.. todo:: List assumptions (rez will run inside an internal network, we assume good intentions, package definitions are written in python and executed). Access to shared filesystem.
.. todo:: File permissions
.. todo:: How to mitigate risks

Main features
=============

There is two main functionalities: building packages and resolving packages. Building a package could imply downloading
and executing code. We don't control how a package is built or what happens during a build.

Missing security features
=========================

This is a list of security features that rez currently lacks (as of 3.0.0). Some are not implemented
because they don't make sense for rez, some are missing because we have not yet have time to implement
them.

* No concept of central package registry that studios can download packages from.
* No concept of artifact. Packages today are directories on a file system.
* No concept of package signature (due to the lack of artifact concept).

Security considerations
=======================

Designed to be run within a safe environment
--------------------------------------------

rez was designed to be used in a studio environment where the environment is trusted.

Package definitions are python files
------------------------------------

Package definitions, both for building packages and resulting from a build are Python files (``package.py``) Rez will read and load them in memory at resolve time.

* Packages can inject environment variables into the resulting shells via
  :doc:`package commands <package_commands>`.
* Packages can inject arbitrary commands to be executed when the shells are started
  via :doc:`package commands <package_commands>`.

Config files can be written in YAML or Python
---------------------------------------------

Config files written in Python can contain arbitrary code.

Config files will be loaded from default paths (see :doc:`configuring_rez`). One of the default path is
the user home folder and it can be disabled using :envvar:`REZ_DISABLE_HOME_CONFIG` if this is a security
concern. It's also posssible to tell rez to load them from any arbitrary path using the :envvar:`REZ_CONFIG_FILE`
environment variable which can contain more than one path.

Heavy use of subprocesses and sub-shells
----------------------------------------

It will create new shells via subprocesses.

.. todo:: With that in mind, the main entry points are config files (written in python) and package definition files.

Communication with outside services
===================================

By default rez doesn't communicate with outside services.

AMQP Server
-----------

Send context information, release events, etc.

.. todo:: Expand

memcached Server
----------------

`memcached <https://memcached.org/>`_ can be used to speed up resolves by caching them in memcached. memcached
is a very simple server and it should not be exposed to the internet. The data is sent and stored unencrypted.

See :ref:`resolve-caching` for more information on how to configure rez with a memcached server.
