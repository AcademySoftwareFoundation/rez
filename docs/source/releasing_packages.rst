==================
Releasing packages
==================

Rez packages can be built and deployed to the :data:`release_packages_path`
using the :ref:`rez-release` tool. This tool performs the following actions:

* All :doc:`actions <building_packages>` that the `rez-build` tool performs.
* Executes all configured :data:`release_hooks`.
* Executes all configured `release_vcs`.

This tool generally runs the same as :ref:`rez-build` otherwise. For more
information, see the :doc:`Building Packages <building_packages>` documentation.