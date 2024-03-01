========
Security
========

.. important::
   This page is a work in progress.

TODO: List assumptions (rez will run inside an internal network, we assume good intentions, package definitions are written in python and executed). Access to shared filesystem.

Security Considerations
=======================

The current assumptions are:

* It designed to be used within a studio environment.
* Package definitions, both for building packages and resulting from a build are Python
  files (``package.py``). Rez will read and load them in memory at resolve time.
* Config files can be written in YAML or Python.
* Package definitions and config files written in Python can contain arbitrary code.
* It will create new shells via subprocesses.
* Packages can inject environment variables into the resulting shells via
  :doc:`package commands <package_commands>`.
* Packages can inject arbitrary commands to be executed when the shells are started
  via :doc:`package commands <package_commands>`.

With that in mind, the main entry points are config files (written in python) and package definition files.
Config files will be loaded from default paths and it's also posssible to tell rez
to load them from any arbitrary path using the :envvar:`REZ_CONFIG_FILE`
environment variable which can contain more than one path.

Document that it can talk to memcached and RabbitMQ (AMQP).

* File permissions
* How to mitigate risks
