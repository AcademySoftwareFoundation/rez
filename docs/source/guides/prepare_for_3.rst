=====================
Prepare for rez 3.0.0
=====================

The rez TSC started to prepare to release rez ``3.0.0``. Rez ``3.0.0`` will not be
a major breaking change but will still remove some things.

This guide will show you how to prepare in advance before ``3.0.0`` is released so
that you are not caught by surprise by the changes made in ``3.0.0`` once you start
using ``3.0.0``. We hope that this guide will help make the upgrade process smoother.

Steps for smooth upgrade
========================

#. Read the `release notes <../CHANGELOG.html>`_ for ``2.114.0`` and ``3.0.0`` (once released). The release
   notes will contain a list of everything that was deprecated in ``2.114.0`` and will
   be removed or changed in ``3.0.0``.

#. Upgrade to ``2.114.0``.

   To upgrade to (or before upgrading to) rez ``3.0.0``, we suggest that you first
   upgrade to ``2.114.0``. This is not mandatory and you can jump straight to ``3.0.0``
   if you wish.
   
   .. warning::
   
      If you skip this step, you won't be able to see deprecation warnings before
      things are removed frm the rez code base.

#. Set the ``REZ_LOG_DEPRECATION_WARNINGS`` environment variable.

   ``2.114.1`` adds a new environment variable called :envvar:`REZ_LOG_DEPRECATION_WARNINGS`
   that will force all rez related deprecation warnings to be printed out to stderr.
   This will let you catch if you are using something deprecated that will be removed
   in future versions.

#. Run rez in you production workflows if possible and watch out for deprecation warnings
   coming from rez.

#. Address each warning one by one.

#. Once you think you have addressed all warnings, upgrade to 3.0.0 (or wait for ``3.0.0`` to
   be released if it's not yet available).

Optional
========

Since some default configuration default values will change in ``3.0.0``, we highly suggest
that you run some anslysis scripts to see if you will be impacted by these changes.

Detect old-style commands in your repositories
----------------------------------------------

Verify that your package repositories don't contain packages that
use old-style commands.

You can use this python snippet to discover all your packages and variants
that contain old style commands. It will print a colored warning for every
package/variant that use old-style commands.

.. code-block:: python

   from rez.config import config
   from rez.packages import iter_packages, iter_package_families

   config.warn_old_commands = True
   config.error_old_commands = False
   config.disable_rez_1_compatibility = False

   for family_name in iter_package_families():
      packages = iter_packages(family_name.name)

      for package in packages:
         package.validate_data()

         for variant in package.iter_variants():
               variant.validate_data()

.. hint::

   Remember to run it over all your repositories!

If you see any warnings, we suggest that you move or remove the packages/variants
from your repositories. This might require some work but it should hopefully not
be too difficult.
