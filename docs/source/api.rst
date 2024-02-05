==========
Python API
==========

.. warning::
   Please note the following warnings prior to using the Rez Python API:

   * We try our best to not break users, but there are no compatibility guarantees between different versions of Rez.
   * The Python API does not currently support rereading from configuration files, or changing to new configuration files after the Python API has initially been imported. If you need to support this functionality, prefer the CLI instead.

.. autosummary::
   :toctree: api
   :recursive:

   rez.build_process
   rez.build_system
   rez.bundle_context
   rez.command
   rez.config
   rez.developer_package
   rez.exceptions
   rez.package_cache
   rez.package_copy
   rez.package_filter
   rez.package_help
   rez.package_maker
   rez.package_move
   rez.package_order
   rez.package_py_utils
   rez.package_remove
   rez.package_repository
   rez.package_resources
   rez.package_search
   rez.package_serialise
   rez.package_test
   rez.packages
   rez.plugin_managers
   rez.release_hook
   rez.release_vcs
   rez.resolved_context
   rez.resolver
   rez.rex_bindings
   rez.rex
   rez.serialise
   rez.shells
   rez.solver
   rez.status
   rez.suite
   rez.system
   rez.util
   rez.utils
   rez.version
   rez.wrapper
