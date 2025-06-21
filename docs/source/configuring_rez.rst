===============
Configuring rez
===============

Rez has a good number of configurable settings. The default settings, and
documentation for every setting, can be found :gh-rez:`src/rez/rezconfig.py`.

Settings are determined in the following way:

- The setting is first read from the file ``rezconfig.py`` in the rez installation;
- The setting is then overridden if it is present in another settings file pointed at by the
  :envvar:`REZ_CONFIG_FILE` environment variable. This can also be a path-like variable, to read from
  multiple configuration files;
- The setting is further overriden if it is present in ``$HOME/.rezconfig`` or ``$HOME/.rezconfig.py``;
- The setting is overridden again if the environment variable :envvar:`REZ_XXX` is present, where ``XXX`` is
  the uppercase version of the setting key. For example, :data:`.image_viewer` will be overriden by
  :envvar:`REZ_IMAGE_VIEWER`.
- This is a special case applied only during a package build or release. In this case, if the
  package definition file contains a "config" section, settings in this section will override all
  others. See :ref:`configuring-rez-package-overrides`.

It is fairly typical to provide your site-specific rez settings in a file that the environment
variable :envvar:`REZ_CONFIG_FILE` is then set to for all your users.

.. tip::
   You do not need to provide a copy of all settings in this file. Just provide those
   that are changed from the defaults.

Supported Configuration File Formats
====================================

Rez supports both YAML configuration files (``.rezconfig``) and Python configuration files (``.rezconfig.py``).

You may prefer a Python based configuration file if you need to vary your configuration settings based on your
current platform.

.. _configuring-rez-settings-merge-rules:

Settings Merge Rules
====================

When multiple configuration sources are present, the settings are merged together -
one config file does not replace the previous one, it overrides it. By default, the
following rules apply:

* Dicts are recursively merged together;
* Non-dicts override the previous value.

However, it is also possible to append and/or prepend list-based settings by using the
:class:`ModifyList <.ModifyList>` class. For example, the
following config entry will append to the :data:`.release_hooks` setting value defined by the
previous configuration sources (you can also supply a ``prepend`` argument):

.. code-block:: python

   release_hooks = ModifyList(append=["custom_release_notify"])

.. _configuring-rez-package-overrides:

Package Overrides
=================

.. todo:: Properly document the scope function as a function that takes a string, etc and make it referenceable.

Packages themselves can override configuration settings. To show how this is useful,
consider the following example:

.. code-block:: python

   # in package.py
   with scope("config") as c:
       c.release_packages_path = "/svr/packages/internal"

Here a package is overriding the default release path - perhaps you're releasing
internally- and externally-developed packages to different locations, for example.

These config overrides are only applicable during building and releasing of the package.
As such, even though any setting can be overridden, it's only useful to do so for
those that have any effect during the build/install process. These include:

* Settings that determine where packages are found, such as :data:`.packages_path`,
  :data:`.local_packages_path` and :data:`.release_packages_path`;
* Settings in the ``build_system``, ``release_hook`` and ``release_vcs`` plugin types;
* :data:`.package_definition_python_path`;
* :data:`.package_filter`.

.. _configuring-rez-string-expansions:

String Expansions
=================

The following string expansions occur on all configuration settings:

* Any environment variable reference, in the form ``${HOME}``;
* Any property of the ``system`` object, eg ``{system.platform}``. See :class:`rez.system.System` for more details.

.. _configuring-rez-delay-load:

Delay Load
==========

It is possible to store a config setting in a separate file, which will be loaded
only when that setting is referenced. This can be useful if you have a large value
(such as a dict) that you don't want to pollute the main config with. YAML and
JSON formats are supported:

.. code-block:: python

   # in rezconfig
   default_relocatable_per_package = DelayLoad('/svr/configs/rez_relocs.yaml')

See :Class:`.DelayLoad`.

.. _configuring-rez-commandline-line:

Commandline Tool
================

You can use the :ref:`rez-config` command line tool to see what the current configured settings are.
Called with no arguments, it prints all settings; if you specify an argument, it prints out just
that setting::

   ]$ rez-config packages_path
   - /home/sclaus/packages
   - /home/sclaus/.rez/packages/int
   - /home/sclaus/.rez/packages/ext

Here is an example showing how to override settings using your own configuration file::

   ]$ echo 'packages_path = ["~/packages", "/packages"]' > myrezconfig.py
   ]$ export REZ_CONFIG_FILE=${PWD}/myrezconfig.py
   ]$ rez-config packages_path
   - /home/sclaus/packages
   - /packages

.. _configuring-rez-configuration-settings:

Configuration Settings
======================

Following is an alphabetical list of rez settings.

.. note::
   Note that this list has been generated automatically from the :gh-rez:`src/rez/rezconfig.py`
   file in the rez source, so you can also refer to that file for the same information.

.. This is a custom directive. See the rez_sphinxext.py file for more information.
.. TL;DR: It will take care of generating the documentation or all the settings defined
.. in rezconfig.py
.. rez-config::
