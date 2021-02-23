## Overview

Package caching is a feature that copies package payloads onto local disk in
order to speed up runtime environments. For example, if your released packages
reside on shared storage (which is common), then running say, a Python process,
will fetch all source from the shared storage across your network. The point of
the cache is to copy that content locally instead, and avoid the network cost.

> [[media/icons/info.png]] Please note: Package caching does _NOT_ cache package
> definitions - only their payloads (ie, the package root directory).

## Enabling

Package caching is not enabled by default. To enable it, you need to configure
[cache_packages_path](Configuring-Rez#cache_packages_path) to specify a path to
store the cache in.

You also have granular control over whether an individual package will or will
not be cached. To make a package cachable, you can set `cachable = True` in its
package definition file. Reasons you may _not_ want to do this include packages
that are large, or that aren't relocatable because other compiled packages are
linked to them in a way that doesn't support library relocation.

There are also config settings that affect cachability in the event that `cachable`
is not defined in a package's definition. For example, see
[default_cachable](Configuring-Rez#default_cachable),
[default_cachable_per_package](Configuring-Rez#default_cachable_per_package)
and [default_cachable_per_repository](Configuring-Rez#default_cachable_per_repository).

Note that you can also disable package caching on the command line, using
`rez-env --no-pkg-caching`.

## Verifying

When you resolve an environment, you can see which variants have been cached by
noting the `cached` label in the righthand column of the `rez-context` output,
as shown below:

```
]$ rez-env Flask

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
```

For reference, cached packages also have their original payload location stored to
an environment variable like so:

```
]$ echo $REZ_FLASK_ORIG_ROOT
/svr/packages/Flask/1.1.2/88a70aca30cb79a278872594adf043dc6c40af99
```

## How it Works

Package caching actually caches _variants_, not entire packages. When you perform
a resolve, or source an existing context, the variants required are copied to
local disk asynchronously (if they are cachable), in a separate process called
`rez-pkg-cache`. This means that a resolve will not necessarily use the cached
variants that it should, the first time around. Package caching is intended to have
a cumulative effect, so that more cached variants will be used over time. This is
a tradeoff to avoid blocking resolves while variant payloads are copied across
your network (and that can be a slow process).

Note that a package cache is **not** a package repository. It is simply a store
of variant payloads, structured in such a way as to be able to store variants from
any package repository, into the one shared cache.

Variants that are cached are assumed to be immutable - no check is done to see if
a variant's payload has changed, and needs to replace an existing cache entry. So
you should _not_ enable caching on package repositories where packages may get
overwritten. It is for this reason that caching is disabled for local packages by
default (see [package_cache_local](Configuring-Rez#package_cache_local)).

## Commandline Tool

### Inspection

Use the `rez-pkg-cache` tool to view the state of the cache, and to perform
warming and deletion operations. Example output follows:

```
]$ rez-pkg-cache
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

```

Each variant is stored into a directory based on a partial hash of that variant's
unique identifier (its "handle"). The package cache is thread- and multiprocess-
proof, and uses a file lock to control access where necessary.

Cached variants have one of the following statuses at any given time:

* **copying**: The variant is in the process of being copied into the cache, and is not
  yet available for use;
* **cached**: The variant has been cached and is ready for use;
* **stalled**: The variant was getting copied, but something went wrong and there is
  now a partial copy present (but unused) in the cache.

### Logging

Caching operations are stored into logfiles within the cache directory. To view:

```
]$ rez-pkg-cache --logs
rez-pkg-cache 2020-05-23 16:17:45,194 PID-29827 INFO Started daemon
rez-pkg-cache 2020-05-23 16:17:45,201 PID-29827 INFO Started caching of variant /home/ajohns/packages/Werkzeug/1.0.1/package.py[0]...
rez-pkg-cache 2020-05-23 16:17:45,404 PID-29827 INFO Cached variant to /home/ajohns/package_cache/Werkzeug/1.0.1/fe76/a in 0.202576 seconds
rez-pkg-cache 2020-05-23 16:17:45,404 PID-29827 INFO Started caching of variant /home/ajohns/packages/python/3.7.4/package.py[0]...
rez-pkg-cache 2020-05-23 16:17:46,006 PID-29827 INFO Cached variant to /home/ajohns/package_cache/python/3.7.4/ce1c/a in 0.602037 seconds
```

### Cleaning The Cache

Cleaning the cache refers to deleting variants that are stalled or no longer in use.
It isn't really possible to know whether a variant is in use, so there is a
configurable [package_cache_max_variant_days](Configuring-Rez#package_cache_max_variant_days)
setting, that will delete variants that have not been used (ie that have not appeared
in a created or sourced context) for more than N days.

You can also manually remove variants from the cache using `rez-pkg-cache -r`.
Note that when you do this, the variant is no longer available in the cache,
however it is still stored on disk. You must perform a clean (`rez-pkg-cache --clean`)
to purge unused cache files from disk.

You can use the [package_cache_clean_limit](Configuring-Rez#package_cache_clean_limit)
setting to asynchronously perform some cleanup every time the cache is updated. If
you do not use this setting, it is recommended that you set up a cron or other form
of execution scheduler, to run `rez-pkg-cache --clean` periodically. Otherwise,
your cache will grow indefinitely.

Lastly, note that a stalled variant will not attempt to be re-cached until it is
removed by a clean operation. Using `package_cache_clean_limit` will not clean
stalled variants either, as that could result in a problematic variant getting
cached, then stalled, then deleted, then cached again and so on. You must run
`rez-pkg-cache --clean` to delete stalled variants.
