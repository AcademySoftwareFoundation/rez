==========================
Developing your own plugin
==========================

This guide will walk you through writing a rez plugin.

.. warning::
   This section is under constructions. The instructions provided might not be
   accurate or up-to-date. We welcome contributions!

Structure
=========

If you decide to register your plugin using the :ref:`entry-points method <plugin-entry-points>`, you are free
to structure your plugin however you like.

If you decide to implement your plugins using the ``rezplugins`` namespace package, please
refer to :ref:`rezplugins-structure` to learn about the file structure that you will need to follow.

Registering subcommands
=======================

Optionally, plugins can provide new ``rez`` subcommands.

To register a plugin and expose a new subcommand, the plugin module:

- **MUST** have a module-level docstring (used as the command help)
- **MUST** provide a ``setup_parser()`` function
- **MUST** provide a ``command()`` function
- **MUST** provide a ``register_plugin()`` function
- **SHOULD** have a module-level attribute ``command_behavior``

For example, a plugin named ``foo`` and this is the ``foo.py`` in the plugin type
root directory:

.. code-block:: python
   :caption: foo.py

   """The docstring for command help, this is required."""
   import argparse

   command_behavior = {
       "hidden": False,   # optional: bool
       "arg_mode": None,  # optional: None, "passthrough", "grouped"
   }


   def setup_parser(parser: argparse.ArgumentParser):
       parser.add_argument("--hello", action="store_true")


   def command(
       opts: argparse.Namespace,
       parser: argparse.ArgumentParser,
       extra_arg_groups: list[list[str]],
   ):
       if opts.hello:
           print("world")


   def register_plugin():
       """This function is your plugin entry point. Rez will call this function."""

       # import here to avoid circular imports.
       from rez.command import Command

       class CommandFoo(Command):
           # This is where you declare the settings the plugin accepts.
           schema_dict = {
               "str_option": str,
               "int_option": int,
           }

           @classmethod
           def name(cls):
               return "foo"

       return CommandFoo

Install plugins
===============

1. Copy directly to rez install folder

   To make your plugin available to rez, you can install it directly under
   ``src/rezplugins`` (that's called a namespace package).

2. Add the source path to :envvar:`REZ_PLUGIN_PATH`

   Add the source path to the ``REZ_PLUGIN_PATH`` environment variable in order to make your plugin available to rez.

3. Add entry points to pyproject.toml

   To make your plugin available to rez, you can also create an entry points section in your
   ``pyproject.toml`` file, that will allow you to install your plugin with ``pip install`` command.

   .. code-block:: toml
      :caption: pyproject.toml

       [build-system]
       requires = ["hatchling"]
       build-backend = "hatchling.build"

       [project]
       name = "foo"
       version = "0.1.0"

       [project.entry-points."rez.plugins"]
       foo_cmd = "foo"

4. Create a setup.py

   To make your plugin available to rez, you can also create a ``setup.py`` file,
   that will allow you to install your plugin with ``pip install`` command.

   .. code-block:: python
      :caption: setup.py

       from setuptools import setup, find_packages

       setup(
           name="foo",
           version="0.1.0",
           package_dir={
               "foo": "foo"
           },
           packages=find_packages(where="."),
           entry_points={
               'rez.plugins': [
                   'foo_cmd = foo',
               ]
           }
       )
