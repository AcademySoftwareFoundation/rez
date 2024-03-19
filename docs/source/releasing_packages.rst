==================
Releasing packages
==================

Rez packages can be built and deployed to the :data:`release_packages_path`
using the :ref:`rez-release` tool. This tool performs the following actions:

* All :doc:`actions <building_packages>` that the ``rez-build`` tool performs.
* Executes all configured :data:`release_hooks`.
* Executes all configured `release_vcs`.

When to release vs build
============================
Packages *can* be installed to the :data:`release_packages_path` manually
by running ``rez-build <release_packages_path>``, so why would you use
``rez-release``?

Well, here are a few benefits of ``rez-release``:

* The package will automatically go to the configured :data:`release_packages_path`, whereas :ref:`rez-build` will go to the :data:`local_packages_path` by default.
* Tests being run by with the :ref:`rez-test` tool can run specifically prior to release, ensuring that releases pass any configured tests first.
* Automatic sanity checks to ensure local repo is ready for release.
* Automatic VCS tagging.
* Many :ref:`helpful package attributes <release-package-attributes>` added to the released `package.py` at build time.

If you're working locally, it these additional steps and checks may slow you
down, so it may be better to stick with :ref:`rez-build`.
