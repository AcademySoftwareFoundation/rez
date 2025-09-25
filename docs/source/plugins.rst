=======
Plugins
=======

Rez is designed around the concept of plugins. Plugins can be used to extend rez's functionalities without modifying any of rez's source code.

Rez comes with built-in plugins that are located at :gh-rez:`src/rezplugins`. New plugins are encouraged to be developed out-of-tree (outside rez).

This page documents what plugins are available, the plugin types and how plugins are discovered.
If you want to learn how to develop a plugin, please refer to :doc:`guides/developing_your_own_plugin`.

.. _plugin-types:

Existing plugin types
=====================

.. table::
   :align: left

   ====================== =========================================================== ==================
   Type                   Base class(es)                                              Top level settings [1]_
   ====================== =========================================================== ==================
   ``build_process``      | :class:`rez.build_process.BuildProcess`
                          | :class:`rez.build_process.BuildProcessHelper` [2]_        No
   ``build_system``       :class:`rez.build_system.BuildSystem`                       No
   ``command``            :class:`rez.command.Command`                                Yes
   ``package_repository`` | :class:`rez.package_repository.PackageRepository`         No
                          | :class:`rez.package_resources.PackageFamilyResource`
                          | :class:`rez.package_resources.PackageResourceHelper`
                          | :class:`rez.package_resources.VariantResourceHelper` [3]_
   ``release_hook``       :class:`rez.release_hook.ReleaseHook`                       Yes
   ``release_vcs``        :class:`rez.release_vcs.ReleaseVCS`                         Yes
   ``shell``              :class:`rez.shells.Shell`                                   No
   ====================== =========================================================== ==================

.. [1] Top level settings: The concept of top level settings is documented in :ref:`default-settings`.
.. [2] build_process: You have to choose between on of the two classes.
.. [3] package_repository: All 4 classes have to be implemented.

.. _configuring-plugins:

Configuring plugins
===================

Plugins can be configured by adding a ``plugins`` key to your ``rezconfig.py``
like this:

.. code-block:: python

   plugins = {
       "package_repository": {
           "filesystem": {}
       }
   }

List installed plugins
======================

Currently installed plugins can be queried by running :option:`rez -i`

.. code-block:: console

   $ rez -i

   Rez 2.113.0

   PLUGIN TYPE         NAME        DESCRIPTION                                        STATUS
   -----------         ----        -----------                                        ------
   build process       local       Builds packages on local host                      loaded
   build process       remote      Builds packages on remote hosts                    loaded
   build system        cmake       CMake-based build system                           loaded
   build system        custom      Package-defined build command                      loaded
   build system        make        Make-based build system                            loaded
   package repository  filesystem  Filesystem-based package repository                loaded
   package repository  memory      In-memory package repository                       loaded
   release hook        amqp        Publishes a message to the broker.                 loaded
   release hook        command     Executes pre- and post-release shell commands      loaded
   release hook        emailer     Sends a post-release email                         loaded
   release vcs         git         Git version control                                loaded
   release vcs         hg          Mercurial version control                          loaded
   release vcs         stub        Stub version control system, for testing purposes  loaded
   release vcs         svn                                                            FAILED: No module named 'pysvn'
   shell               cmd         Windows Command Prompt (DOS) shell.                loaded
   shell               gitbash     Git Bash (for Windows) shell                       loaded
   shell               powershell  Windows PowerShell 5                               loaded
   shell               pwsh        PowerShell Core 6+                                 loaded

Discovery mechanisms
====================

There are three different discovery mechanisms for external/out-of-tree plugins:

#. :ref:`rezplugins-structure`
#. :ref:`plugin-entry-points`

Each of these mechanisms can be used independently or in combination. It is up to you to
decide which discovery mechanism is best for your use case. Each option has pros and cons.

.. _rezplugins-structure:

``rezplugins`` structure
------------------------

This method relies on the ``rezplugins`` namespace package. Use the :data:`plugin_path` setting or
the :envvar:`REZ_PLUGIN_PATH` environment variable to tell rez where to find your plugin(s).

You need to follow the following file structure:

.. code-block:: text

   rezplugins/
   ├── __init__.py
   └── <plugin_type>/
       ├── __init__.py
       └── <plugin name>.py

``<plugin_type>`` refers to types defined in the :ref:`plugin types <plugin-types>` section. ``<plugin_name>`` is the name of your plugin.
The ``rezplugins`` directory is not optional.

.. note::
    The path(s) MUST point to the directory **above** your ``rezplugins`` directory.

.. note::
   Even though ``rezplugins`` is a python package, your sparse copy of
   it should  not be on the :envvar:`PYTHONPATH`, just the :envvar:`REZ_PLUGIN_PATH`.
   This is important  because it ensures that rez's copy of
   ``rezplugins`` is always found first.

.. _plugin-entry-points:

Entry-points
------------

.. versionadded:: 3.3.0

Plugins can be discovered by using `Python's entry-points <https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-package-metadata>`_.

There is one entry-point per :ref:`plugin type <plugin-types>`:

* ``rez.plugins.build_process``
* ``rez.plugins.build_system``
* ``rez.plugins.command``
* ``rez.plugins.package_repository``
* ``rez.plugins.release_hook``
* ``rez.plugins.release_vcs``
* ``rez.plugins.shell``

This allows a package to define multiple plugins. In fact, a package can contain multiple plugins of the same type and plugins for multiple types.

.. note::
   Unlike the other discovery mechanisms, this method doesn't require any special file structure. It is thus more flexible, less restricting
   and easier to use.

.. _default-settings:

Default settings
----------------

You can define default settings for the plugins you write by adding a ``rezconfig.py`` or ``rezconfig.yml``
beside your plugin module. Rez will automatically load these settings.

This is valid both all the discovery mechanisms.

Note that the format of that ``rezconfig.py`` or ``rezconfig.yml`` file for plugins is as follows:

.. code-block:: python

   top_level_setting = "value"

   plugin_name = {
       "setting_1": "value1"
   }

In this case, the settings for ``plugin_name`` would be available in your plugin as ``self.settings``
and ``top_level_setting`` would be available as ``self.type_settings.top_level_setting``.

.. note::

   Not all plugin types support top level settings. Please refer to the table in :ref:`plugin-types` to
   see which types support them.

Overriding built-in plugins
===========================

Built-in plugins can be overridden by installing a plugin with the same name and type.
When rez sees this, it will prioritie your plugin over its built-in plugin.

This is useful if you want to modify a built-in plugin without having to modify rez's source code.
