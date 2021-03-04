## Overview

_Introduced in version 2.71.0_

Ephemeral packages (or simply 'ephemerals') are requests for packages that do not
exist. Ephemeral package names always begin with a dot (`.`). Like all package
requests, ephemerals can be requested as part of packages' requires or variants
lists, or directly by the user (via `rez-env` for eg).

Example:

    ]$ rez-env .foo-1
    You are now in a rez-configured environment.

    resolved by ajohns@turtle, on Tue Dec 22 08:17:00 2020, using Rez v2.70.0

    requested packages:
    .foo-1             (ephemeral)
    ~platform==linux   (implicit)
    ~arch==x86_64      (implicit)
    ~os==Ubuntu-16.04  (implicit)

    resolved packages:
    .foo-1    (ephemeral)

Ephemerals will act like real packages during a resolve - ie, their request ranges
will intersect, and conflicts can occur - but they never actually correlate to a
real package, nor do they perform any configuration on the runtime (not directly
in any case).

Example showing range intersection:

    ]$ rez-env .foo-1 '.foo-1.5+'

    You are now in a rez-configured environment.

    resolved by ajohns@turtle, on Tue Dec 22 08:21:04 2020, using Rez v2.70.0

    requested packages:
    .foo-1             (ephemeral)
    .foo-1.5+          (ephemeral)
    ~platform==linux   (implicit)
    ~arch==x86_64      (implicit)
    ~os==Ubuntu-16.04  (implicit)

    resolved packages:
    .foo-1.5+<1_    (ephemeral)

Example of conflicting request:

    ]$ rez-env .foo-1 .foo-2
    The context failed to resolve:
    The following package conflicts occurred: (.foo-1 <--!--> .foo-2)

## Environment Variables

Ephemerals do not affect the runtime in the way that packages can (via their
`commands` section), however some environment variables are set:

* `REZ_USED_EPH_RESOLVE` lists all resolved ephemeral requests;
* `REZ_EPH_(PKG)_REQUEST` is set for every resolved ephemeral. Here, `(PKG)` is
  the ephemeral name, in uppercase, with dots replaced by underscores and with
  **the leading dot removed**.

The following example illustrates:

    ]$ rez-env python .foo-1 .bah-2
    ...
    ]$ echo $REZ_EPH_FOO_REQUEST
    1
    ]$ echo $REZ_USED_EPH_RESOLVE
    .foo-1 .bah-2

## Introspection

In order for a package to inspect the ephemerals that are present in a runtime,
there is an [ephemerals](Package-Commands#ephemerals) object provided, similar
to the [resolve](Package-Commands#resolve) object. You would typically use the
[intersects](Package-Commands#intersects) function to inspect it, like so:

    # in package.py
    def commands()
        if intersects(ephemerals.get_range('enable_tracking', '0'), '1'):
            env.TRACKING_ENABLED = 1

In this example, the given package would set the `TRACKING_ENABLED` environment
variable if an ephemeral such as `.enable_tracking-1` (or `.enable_tracking-1.2+`
etc) is present in the resolve. Note that the leading `.` is implied and not
included when querying the `ephemerals` object.

> [[media/icons/warning.png]] Since `ephemerals` is a dict-like object, so it has
> a `get` function which will return a full request string if key exists. Hence,
> the default value should also be a full request string, not just a version range
> string like `'0'` in `get_range`. Or `intersects` may not work as expect. 

## Ephemeral Use Cases

Why would you want to request packages that don't exist? There are two main use
cases.

### Passing Information to Packages

Ephemerals can be used as a kind of 'package option', or a way to pass information
to packages in a resolve. For example, consider the following package definition:

    name = 'bah'

    def commands():
        if intersects(ephemerals.get_range('bah.cli', '1'), '1'):
            env.PATH.append('{root}/bin')

This package will disable its command line tools if an ephemeral like `.bah.cli-0`
is present in the runtime.

> [[media/icons/info.png]] Ephemerals are standard package requests and so can
> have any range, such as `1.2.3`, `2.5+` and so on. However, they're often used
> as boolean package options, as in the example above. In this case, it is
> recommended to use the conventional ranges `1` and `0` to designate true and
> false.

Since ephemerals can be pretty much anything, you might also decide to use them
as a global package option. Here's another take on our example, but in this case
we introduce a `.cli` ephemeral that acts as a global whitelist:

    name = 'bah'

    def commands():
        if intersects(ephemerals.get_range('cli', ''), 'bah'):
            env.PATH.append('{root}/bin')

Here, all packages' cli will be enabled if `.cli` is not specified, but if it is
specified then it acts as a whitelist:

    # turn on cli for foo and bah only
    ]$ rez-env foo-1 bah==2.3.1 eek-2.4 '.cli-foo|bah'

### Abstract Package Representation

Sometimes it makes sense for a package to require some form of abstract object or
capability, rather than an actual package. For example, perhaps your package (or
one of its variants) requires a GPU to be present on the host machine. To support
this, you might have something setup that includes a `.gpu-1` ephemeral in the
[implicits](Basic-Concepts#implicit-packages) list on all GPU-enabled hosts.
Then, your package could look like this:

    name = 'pixxelator'

    variants = [
        ['.gpu-0'],  # renders via CPU
        ['.gpu-1']  # renders via GPU
    ]

> [[media/icons/warning.png]] Be aware that on hosts that do _not_ have a gpu
> implicit, either variant could be selected. You would want to either guarantee
> that every host has the gpu implicit set to 0 or 1, or that the user always
> explicitly specifies `.gpu-0` or `.gpu-1` in their request.
