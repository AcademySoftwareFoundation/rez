============================
Linking to rez documentation
============================

Sphinx projects can use `intersphinx <https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html>`_
to link to objects in the rez documentation. Rez provides the
``rez.utils.sphinxext`` Sphinx extension for its two custom domains:

``pkgdef``
   Package definition attributes and functions documented in
   :doc:`../package_definition`.

``rex``
   Objects available to package commands documented in
   :doc:`../package_commands`.

Configuration
=============

Install rez and Sphinx in the environment that builds your documentation. Rez
does not install or pin Sphinx, so your project can select the appropriate Sphinx
version.

Add the rez extension and intersphinx mapping to your Sphinx ``conf.py`` file:

.. code-block:: python

   extensions = [
       "sphinx.ext.intersphinx",
       "rez.utils.sphinxext",
   ]

   intersphinx_mapping = {
       "rez": ("https://docs.rez-project.io/en/stable/", None),
   }

If your project already defines ``extensions`` or ``intersphinx_mapping``, add
these entries to the existing values instead of replacing them.

Creating links
==============

Use an explicit external reference to select the rez inventory, domain, and
object type:

.. code-block:: rst

   :external+rez:pkgdef:attr:`requires`
   :external+rez:pkgdef:func:`commands`
   :external+rez:rex:attr:`this.root`
   :external+rez:rex:func:`alias`

The ``external+rez`` prefix selects the ``rez`` entry in
``intersphinx_mapping``. The next two components select the domain and role.

Compatibility
=============

Rez intentionally keeps this integration small and does not install or pin a
Sphinx version. Documentation projects can select and manage the Sphinx version
appropriate for their own builds.

We aim to keep ``rez.utils.sphinxext`` compatible across Sphinx and rez releases, but
not every combination is guaranteed. Changes to Sphinx's domain or intersphinx
APIs may require an updated rez extension. For reproducible documentation
builds, projects should pin their documentation dependencies and treat
unresolved references as errors.
