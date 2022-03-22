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


## Patching Libraries

Depending on how compiled libraries and executables within a rez package were
built, it's possible that the dynamic linker will attempt to resolve them to
libraries found outside of the bundle. For example, this is possible in linux
if an elf contains an absolute searchpath in its rpath/runpath header to a
library in another package.

Rez bundling performs a library patching step that applies various fixes to
solve this issue (use `--no-lib-patch` if you want to skip this step). This step
is platform-specific and is covered in the following sections. Note that in all
cases, references to libraries outside of the bundle will remain intact, if there
is no equivalent path found within the bundle (for example, if the reference is
to a system library not provided by a rez package).

### Linux

On linux, rpath/runpath headers are altered if paths are found that map to a
subdirectory within another package in the bundle. To illustrate what happens,
consider the following example, where packages from `/sw/packages` have been
bundled into the local directory `./mybundle`:

```
]$ # a lib in an original non-bundled package
]$ patchelf --print-rpath /sw/packages/foo/1.0.0/bin/foo
/sw/packages/bah/2.1.1/lib
]$
]$ # the same lib in our bundle. We assume that package 'bah' is in the bundle
]$ # also, since foo links to one of its libs
]$ patchelf --print-rpath ./mybundle/packages/foo/1.0.0/bin/foo
$ORIGIN/../../../bah/2.1.1/lib
```

Remapped rpaths make use of the special `$ORIGIN` variable, which refers to
the directory containing the current file.
