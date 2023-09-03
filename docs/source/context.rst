=======
Context
=======

When you use :ref:`rez-env` to create a resolved environment, you are actually
creating something called a *context*. A context is a store of information
including:

* The initial :ref:`package request <package-requests-concept>` list;
* The *resolve* (the list of variants that were chosen);
* A graph which shows the resolve visually.

The context does not store copies of the packages it resolved to; rather, it
stores a kind of handle for each, which gives enough information to know where
to fetch the full package definition and contents from.

Contexts themselves are quite small, and are stored in JSON format in a file
with the extension ``rxt``. When you use :ref:`rez-env`, it actually creates a temporary
context file on disk, which is removed when the shell is exited:

.. code-block:: console

   $ rez-env foo bah

   You are now in a rez-configured environment.

   resolved by ajohns@14jun01.methodstudios.com, on Wed Oct 22 12:44:00 2014,
   using Rez v2.0.rc1.10

   requested packages:
   foo
   bah

   resolved packages:
   eek-2.6   /packages/inhouse/eek/2.6
   foo-1.2   /packages/inhouse/foo/1.2
   bah-4     /packages/inhouse/bah/4

   > $ echo $REZ_RXT_FILE
   /tmp/rez_context_0tMS4U/context.rxt

.. _context-baking-resolves:

Baking Resolves
===============

You can use the :option:`rez-env --output` flag to write a resolved context directly
to file, rather than invoking a subshell:

.. code-block:: console

   $ rez-env foo bah --output test.rxt

Later, you can read the context back again, to reconstruct the same environment:

.. code-block:: console

   $ rez-env --input test.rxt

   You are now in a rez-configured environment.

   resolved by ajohns@14jun01.methodstudios.com, on Wed Oct 22 12:44:00 2014,
   using Rez v2.0.rc1.10

   requested packages:
   foo
   bah

   resolved packages:
   eek-2.6   /packages/inhouse/eek/2.6
   foo-1.2   /packages/inhouse/foo/1.2
   bah-4     /packages/inhouse/bah/4

   > $ █

Contexts do not store a copy of the environment that is configured (that is, the
environment variables exported, for example). A context just stores the resolved
list of packages that need to be applied in order to configure the environment.
When you load a context via :option:`rez-env --input`, each of the packages' :attr:`commands`
sections are interpreted once more.

You can think of package :attr:`commands` like fragments of a wrapper script which
configures an environment. By creating a context, you are creating a list of
script fragments which, when run in serial, produce the target environment. So,
if your package added a path to ``$PATH`` which included a reference to ``$USER``
for example, this would work correctly even if Joe created the rxt file, and
Jill read it because the commands are reinterpreted when Jill loads the context.

The rez-context Tool
====================

The :ref:`rez-context` tool inspects context files. When you're within a resolved
subshell, :ref:`rez-context` inspects the current context, unless one is specified
explicitly. For example, we can inspect the context created in the previous
example, without actually being within it:

.. code-block:: console

   $ rez-context test.rxt

   resolved by ajohns@14jun01.methodstudios.com, on Wed Oct 22 12:44:00 2014,
   using Rez v2.0.rc1.10

   requested packages:
   foo
   bah

   resolved packages:
   eek-2.6   /packages/inhouse/eek/2.6
   foo-1.2   /packages/inhouse/foo/1.2
   bah-4     /packages/inhouse/bah/4
