=======
Plugins
=======

Rez is designed around the concept of plugins. Plugins can be used to extend rez's functionalities without modifying any of rez's source code.

Plugins are currently bundled in the main rez repo, but will be split out
to their own repos in the future.

The built-in plugins are located at :gh-rez:`src/rezplugins`.

Loaded plugins
==============

Currently loaded plugins can be queried by running ``rez -i``

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

Existing plugin types
=====================

- :gh-rez:`src/rezplugins/build_process`
- :gh-rez:`src/rezplugins/build_system`
- :gh-rez:`src/rezplugins/command`
- :gh-rez:`src/rezplugins/package_repository`
- :gh-rez:`src/rezplugins/release_hook`
- :gh-rez:`src/rezplugins/release_vcs`
- :gh-rez:`src/rezplugins/shell`

Developing your own plugin
==========================

Rez plugins require a specific folder structure as follows:

.. code-block:: text

    /plugin_type
        /__init__.py (adds plugin path to rez)
        /rezconfig.py (defines configuration settings for your plugin)
        /plugin_file1.py (your plugin file)
        /plugin_file2.py (your plugin file)
        etc.

To make your plugin available to rez, you can install them directly under
``src/rezplugins`` (that's called a namespace package) or you can add
the path to :envvar:`REZ_PLUGIN_PATH`.

Registering subcommands
-----------------------

Optionally, plugins can provide new ``rez`` subcommands.

To register a plugin and expose a new subcommand, the plugin module:

- MUST have a module-level docstring (used as the command help)
- MUST provide a `setup_parser()` function
- MUST provide a `command()` function
- MUST provide a `register_plugin()` function
- SHOULD have a module-level attribute `command_behavior`

For example, a plugin named 'foo' and this is the ``foo.py``:

.. code-block:: python
   :caption: your_plugin_file.py

   '''The docstring for command help, this is required.
   '''
   from rez.command import Command

   command_behavior = {
       "hidden": False,   # optional: bool
       "arg_mode": None,  # optional: None, "passthrough", "grouped"
   }

   def setup_parser(parser, completions=False):
       parser.add_argument("--hello", ...)

   def command(opts, parser=None, extra_arg_groups=None):
       if opts.hello:
           print("world")

   class CommandFoo(Command):
       schema_dict = {}
       @classmethod
       def name(cls):
           return "foo"

   def register_plugin():
       return CommandFoo

Other required file contents
----------------------------
.. code-block:: python
   :caption: __init__.py

    from rez.plugin_managers import extend_path
    __path__ = extend_path(__path__, __name__)


