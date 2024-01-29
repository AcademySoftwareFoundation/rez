=======
Caching
=======

Resolve Caching
===============

Resolve caching is a feature that caches resolves to a `memcached <https://memcached.org/>`_ database.

Memcached is widely used, easy to deploy (because there is no storage needed since it's a single
process/executable), and is very fast due to the data residing in memory.

In a studio environment (with many machines), machines that perform a solve that is already cached to the
resolve cache will simply receive the cached result rather than preforming a re-solve. This can significantly
decrease the time it takes to resolve environments. Slow solves will now be almost instantaneous.

Resolve caching has almost no downsides. Only in rare edge cases where you have to "hack" a released package into
production do you see any issues. In this case, because resolves are cached, you may receive a different package than
you expect. In this case however, it's better to just manually invalidate the cache anyway.

Cache contents
--------------

The following information is stored to the memcached server for each solve:

* Solver information about previously cached solves.
* Timestamps of packages seen in previous solves.
* Variant states information about the state of a variant. For example, in the 'filesystem' repository type,
  the 'state' is the last modified date of the file associated with the variant (perhaps a package.py).
  If the state of any variant has changed from a cached resolve - eg. if a file has been modified - the cached resolve is discarded.

Setup
-----

To enable memcached caching, you need to configure the :data:`memcached_uri` config variable.
This variable accepts a list of URI to your memcached servers or None. Example with memcached running on
localhost on its default port:

.. code-block:: python

   memcached_uri = ["127.0.0.1:11211"]

This is the only parameter you need to configure to enable caching of the content and location of package file definitions and resolutions in Rez.

Please refer to the :ref:`caching <config-caching>` configuration section for a complete list of settings.

Cache invalidation
------------------

Cache entries will automatically be invalidated when a newer package version is released that would change the result
of an existing resolve.

For example, let's say you are running rez-env with the package ``foo1+<2``, and originally, the only available
``foo`` package version is ``1.0.0``, so the cached resolve points to ``1.0.0``. However, at some point afterwards
you release a new version ``1.0.1``. The cache would invalidate for the request ``foo1+<2`` and the next resolve
would correctly retrieve package version ``1.0.1``.

Validating operation
--------------------

To print debugging information about memcached usage, you can set the :envvar:`REZ_DEBUG_MEMCACHE` environment
variable or you can use the :data:`debug_memcache` setting.

Show stats from memcached server
--------------------------------

Rez provides a command-line tool :ref:`rez-memcache` that can be used to see stats about cache misses/hits and to
reset the memcached cache.

.. code-block:: console

   $ rez-memcache

   CACHE SERVER               UPTIME      HITS      MISSES  HIT RATIO  MEMORY  USED
   ------------               ------      ----      ------  ---------  ------  ----
   127.0.0.1:11211            20 hours    27690     5205    84%        119 Gb  10 Mb (0%)
   central.example.com:11211  6.2 months  19145089  456     99%        64 Mb   1.9 Mb (2%)

.. _package-caching:

Package Caching
===============

Package caching is a feature that copies package payloads onto local disk in
order to speed up runtime environments. For example, if your released packages
reside on shared storage (which is common), then running say, a Python process,
will load all source from the shared storage across your network. The point of
the cache is to copy that content locally instead, and avoid the network cost.

.. note::
   Package caching does **NOT** cache package definitions.
   Only their payloads (ie, the package root directory).

Build behavior
--------------

Package caching during a package build is disabled by default. To enable caching during
a package build, you can set :data:`package_cache_during_build` to True.

.. _enabling-package-caching:

Enabling Package Caching
========================

Package caching is not enabled by default. To enable it, you need to configure
:data:`cache_packages_path` to specify a path to
store the cache in.

You also have granular control over whether an individual package will or will
not be cached. To make a package cachable, you can set :attr:`cachable`
to False in its package definition file. Reasons you may *not* want to do this include
packages that are large, or that aren't relocatable because other compiled packages are
linked to them in a way that doesn't support library relocation.

There are also config settings that affect cachability in the event that :attr:`cachable`
is not defined in a package's definition. For example, see
:data:`default_cachable`, :data:`default_cachable_per_package`
and :data:`default_cachable_per_repository`.

Note that you can also disable package caching on the command line, using
:option:`rez-env --no-pkg-cache`.

Verifying
---------

When you resolve an environment, you can see which variants have been cached by
noting the ``cached`` label in the right-hand column of the :ref:`rez-context` output,
as shown below:

.. code-block:: console

   $ rez-env Flask

   You are now in a rez-configured environment.

   requested packages:
   Flask
   ~platform==linux   (implicit)
   ~arch==x86_64      (implicit)
   ~os==Ubuntu-16.04  (implicit)

   resolved packages:
   Flask-1.1.2         /home/ajohns/package_cache/Flask/1.1.2/d998/a                                     (cached)
   Jinja2-2.11.2       /home/ajohns/package_cache/Jinja2/2.11.2/6087/a                                   (cached)
   MarkupSafe-1.1.1    /svr/packages/MarkupSafe/1.1.1/d9e9d80193dcd9578844ec4c2c22c9366ef0b88a
   Werkzeug-1.0.1      /home/ajohns/package_cache/Werkzeug/1.0.1/fe76/a                                  (cached)
   arch-x86_64         /home/ajohns/package_cache/arch/x86_64/6450/a                                     (cached)
   click-7.1.2         /home/ajohns/package_cache/click/7.1.2/0da2/a                                     (cached)
   itsdangerous-1.1.0  /home/ajohns/package_cache/itsdangerous/1.1.0/b23f/a                              (cached)
   platform-linux      /home/ajohns/package_cache/platform/linux/9d4d/a                                  (cached)
   python-3.7.4        /home/ajohns/package_cache/python/3.7.4/ce1c/a                                    (cached)

For reference, cached packages also have their original payload location stored to
an environment variable like so:

.. code-block:: console

   $ echo $REZ_FLASK_ORIG_ROOT
   /svr/packages/Flask/1.1.2/88a70aca30cb79a278872594adf043dc6c40af99

How it Works
------------

Package caching actually caches :doc:`variants`, not entire packages. When you perform
a resolve, or source an existing context, the variants required are copied to
local disk asynchronously (if they are cachable), in a separate process called
:ref:`rez-pkg-cache`. This means that a resolve will not necessarily use the cached
variants that it should, the first time around. Package caching is intended to have
a cumulative effect, so that more cached variants will be used over time. This is
a tradeoff to avoid blocking resolves while variant payloads are copied across
your network (and that can be a slow process).

Note that a package cache is **not** a package repository. It is simply a store
of variant payloads, structured in such a way as to be able to store variants from
any package repository, into the one shared cache.

Variants that are cached are assumed to be immutable. No check is done to see if
a variant's payload has changed, and needs to replace an existing cache entry. So
you should **not** enable caching on package repositories where packages may get
overwritten. It is for this reason that caching is disabled for local packages by
default (see :data:`package_cache_local`).

Commandline Tool
----------------

Inspection
++++++++++

Use the :ref:`rez-pkg-cache` tool to view the state of the cache, and to perform
warming and deletion operations. Example output follows:

.. code-block:: console

   $ rez-pkg-cache
   Package cache at /home/ajohns/package_cache:

   status   package             variant uri                                             cache path
   ------   -------             -----------                                             ----------
   cached   Flask-1.1.2         /svr/packages/Flask/1.1.2/package.py[0]         /home/ajohns/package_cache/Flask/1.1.2/d998/a
   cached   Jinja2-2.11.2       /svr/packages/Jinja2/2.11.2/package.py[0]       /home/ajohns/package_cache/Jinja2/2.11.2/6087/a
   cached   Werkzeug-1.0.1      /svr/packages/Werkzeug/1.0.1/package.py[0]      /home/ajohns/package_cache/Werkzeug/1.0.1/fe76/a
   cached   arch-x86_64         /svr/packages/arch/x86_64/package.py[]          /home/ajohns/package_cache/arch/x86_64/6450/a
   cached   click-7.1.2         /svr/packages/click/7.1.2/package.py[0]         /home/ajohns/package_cache/click/7.1.2/0da2/a
   cached   itsdangerous-1.1.0  /svr/packages/itsdangerous/1.1.0/package.py[0]  /home/ajohns/package_cache/itsdangerous/1.1.0/b23f/a
   cached   platform-linux      /svr/packages/platform/linux/package.py[]       /home/ajohns/package_cache/platform/linux/9d4d/a
   copying  python-3.7.4        /svr/packages/python/3.7.4/package.py[0]        /home/ajohns/package_cache/python/3.7.4/ce1c/a
   stalled  MarkupSafe-1.1.1    /svr/packages/MarkupSafe/1.1.1/package.py[1]    /home/ajohns/package_cache/MarkupSafe/1.1.1/724c/a

Each variant is stored into a directory based on a partial hash of that variant's
unique identifier (its "handle"). The package cache is thread and multiprocess
proof, and uses a file lock to control access where necessary.

Cached variants have one of the following statuses at any given time:

* **copying**: The variant is in the process of being copied into the cache, and is not
  yet available for use;
* **cached**: The variant has been cached and is ready for use;
* **stalled**: The variant was getting copied, but something went wrong and there is
  now a partial copy present (but unused) in the cache.

Logging
+++++++

Caching operations are stored into logfiles within the cache directory. To view:

.. code-block:: console

   $ rez-pkg-cache --logs
   rez-pkg-cache 2020-05-23 16:17:45,194 PID-29827 INFO Started daemon
   rez-pkg-cache 2020-05-23 16:17:45,201 PID-29827 INFO Started caching of variant /home/ajohns/packages/Werkzeug/1.0.1/package.py[0]...
   rez-pkg-cache 2020-05-23 16:17:45,404 PID-29827 INFO Cached variant to /home/ajohns/package_cache/Werkzeug/1.0.1/fe76/a in 0.202576 seconds
   rez-pkg-cache 2020-05-23 16:17:45,404 PID-29827 INFO Started caching of variant /home/ajohns/packages/python/3.7.4/package.py[0]...
   rez-pkg-cache 2020-05-23 16:17:46,006 PID-29827 INFO Cached variant to /home/ajohns/package_cache/python/3.7.4/ce1c/a in 0.602037 seconds

Cleaning The Cache
++++++++++++++++++

Cleaning the cache refers to deleting variants that are stalled or no longer in use.
It isn't really possible to know whether a variant is in use, so there is a
configurable :data:`package_cache_max_variant_days`
setting, that will delete variants that have not been used (ie that have not appeared
in a created or sourced context) for more than N days.

You can also manually remove variants from the cache using :option:`rez-pkg-cache -r`.
Note that when you do this, the variant is no longer available in the cache,
however it is still stored on disk. You must perform a clean (:option:`rez-pkg-cache --clean`)
to purge unused cache files from disk.

You can use the :data:`package_cache_clean_limit`
setting to asynchronously perform some cleanup every time the cache is updated. If
you do not use this setting, it is recommended that you set up a cron or other form
of execution scheduler, to run :option:`rez-pkg-cache --clean` periodically. Otherwise,
your cache will grow indefinitely.

Lastly, note that a stalled variant will not attempt to be re-cached until it is
removed by a clean operation. Using :data:`package_cache_clean_limit` will not clean
stalled variants either, as that could result in a problematic variant getting
cached, then stalled, then deleted, then cached again and so on. You must run
:option:`rez-pkg-cache --clean` to delete stalled variants.
