## Overview

A "context bundle" is a directory containing a context (an rxt file), and a
package repository. All packages in the context are stored in the repository,
making the bundle relocatable and standalone. You can copy a bundle onto a
server for example, or into a container, and there are no external references
to shared package repositories. This is in contrast to a typical context, which
contains absolute references to one or more package repositories that are
typically on shared disk storage.

To create a bundle via command line:

```
]$ rez-env foo -o foo.rxt
]$ rez-bundle foo.rxt ./mybundle

]$ # example of running a command from the bundled context
]$ rez-env -i ./mybundle/context.rxt -- foo-tool
```

To create a bundle via API:

```
>>> from rez.bundle_context import bundle_context
>>> from rez.resolved_context import ResolvedContext
>>>
>>> c = ResolvedContext(["python-3+", "foo-1.2+<2"])
>>> bundle_context(c, "./mybundle")
```


## Structure

A bundle directory looks like this:

```
.../mybundle/
       ./context.rxt
       ./packages/
           <standard package repo structure>
```

Package references in the rxt file are relative (unlike in a standard context,
where they're absolute), and this makes the bundle relocatable.
