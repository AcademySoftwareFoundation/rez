## Overview

Packages can be copied from one [package repository](Basic-Concepts#package-repositories)
to another, like so:

Via commandline:

```
]$ rez-cp --dest-path /svr/packages2 my_pkg-1.2.3
```

Via API:

```
>>> from rez.package_copy import copy_package
>>> from rez.packages import get_latest_package
>>>
>>> p = get_latest_package("python")
>>> p
Package(FileSystemPackageResource({'location': '/home/ajohns/packages', 'name': 'python', 'repository_type': 'filesystem', 'version': '3.7.4'}))

>>> r = copy_package(p, "./repo2")
>>>
>>> print(pprint.pformat(r))
{
    'copied': [
        (
            Variant(FileSystemVariantResource({'location': '/home/ajohns/packages', 'name': 'python', 'repository_type': 'filesystem', 'index': 0, 'version': '3.7.4'})),
            FileSystemVariantResource({'location': '/home/ajohns/repo2', 'name': 'python', 'repository_type': 'filesystem', 'index': 0, 'version': '3.7.4'})
        )
    ],
    'skipped': []
}
```

Copying packages is actually done one variant at a time, and you can copy some
variants of a package if you want, rather than the entire package. The API call's
return value shows what variants were copied - The 2-tuple in `copied` lists the
source (the variant that was copied from) and destination (the variant that was
created) respectively.

> [[media/icons/warning.png]] Do not simply copy package directories on disk -
> you should always use `rez-cp`. Copying directly on disk is bypassing rez and
> this can cause problems such as a stale resolve cache. Using `rez-cp` gives
> you more control anyway.

## Enabling

Copying packages is enabled by default, however you're also able to specify which
packages are and are not _relocatable_, for much the same reasons as given
[here](Package-Caching#enabling).

You can mark a package as non-relocatable by setting `relocatable = False` in its
package definition file. There are also config settings that affect relocatability
in the event that relocatable is not defined in a package's definition. For example,
see [default_relocatable](Configuring-Rez#default_relocatable),
[default_relocatable_per_package](Configuring-Rez#default_relocatable_per_package)
and [default_relocatable_per_repository](Configuring-Rez#default_relocatable_per_repository).

Attempting to copy a non-relocatable package will raise a `PackageCopyError`.
However, note that there is a `force` option that will override this - use at
your own risk.
