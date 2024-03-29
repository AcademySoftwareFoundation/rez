=======
Plugins
=======

Plugins are extensions of rez that extend rez functionality.

Plugins are currently bundled in the main rez repo, but will be split out
to their own repos in the future.

The built-in plugins are located at :gh-rez:`src/rezplugins`.

Existing plugins
================

- :gh-rez:`src/rezplugins/build_process`
- :gh-rez:`src/rezplugins/build_system`
- :gh-rez:`src/rezplugins/command`
- :gh-rez:`src/rezplugins/build_process/package_repository`
- :gh-rez:`src/rezplugins/build_process/release_hook`
- :gh-rez:`src/rezplugins/build_process/release_vcs`
- :gh-rez:`src/rezplugins/build_process/shell`

Developing your own plugin
==========================

Rez plugins require a specific folder structure as follows:

.. code-block:: text

    /plugin_name
        /__init__.py (adds plugin path to rez)
        /rezconfig.py (defines configuration settings for your plugin)
        /plugin_file1.py (your plugin file)
        /plugin_file2.py (your plugin file)
        etc.

To make your plugin available to rez, you can install them directly under
``src/rezplugins`` (that's called a namespace package) or you can add
the path to :envvar:`REZ_PLUGIN_PATH`.

Plugin types
------------

There are two different plugin types in Rez.

- Plugin
- Extension

Extensions differ from standard plugins in that they add a new command to rez's
CLI.

Required file contents
----------------------
``__init__.py``

.. code-block:: python

    from rez.plugin_managers import extend_path
    __path__ = extend_path(__path__, __name__)

``your_plugin_file.py``

.. code-block:: python

    def register_plugin():
        return YourPluginClass