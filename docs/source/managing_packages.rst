=================
Managing packages
=================

Ignoring Packages
=================

Packages can be ignored. When this happens, the package is still present in its
repository, but it will not be visible to the rez API nor to any newly resolved
runtimes. Any runtimes that are currently using an ignored package are unaffected,
since the package's payload has not been removed.

To ignore a package via commandline:

.. code-block:: console

   $ # you need to specify the repo, but you'll be shown a list if you don't
   $ rez-pkg-ignore foo-1.2.3
   No action taken. Run again, and set PATH to one of:
   filesystem@/home/ajohns/packages

   $ rez-pkg-ignore foo-1.2.3 filesystem@/home/ajohns/packages
   Package is now ignored and will not be visible to resolves

Via API:

.. code-block:: python

   >>> from rez.package_repository import package_repository_manager
   >>>
   >>> repo_path = "filesystem@/home/ajohns/packages"
   >>> repo = package_repository_manager.get_repository(repo_path)
   >>> repo.ignore_package("foo", "1.2.3")
   1  # -1: pkg not found; 0: pkg already ignored; 1: pkg ignored

Both of these options generate a :file:`.ignore{{version}}` file (e.g.
``.ignore3.1.2``) next to the package version directory.

You can also do the reverse (ie unignore a package). Use the :option:`-u <rez-pkg-ignore -u>` option of
:ref:`rez-pkg-ignore`, or the :meth:`~rez.package_repository.PackageRepository.unignore_package` method on the package repository
object.

Copying Packages
================

Packages can be copied from one :ref:`package repository <package-repositories-concept>`
to another, like so:

Via commandline:

.. code-block:: console

   $ rez-cp --dest-path /svr/packages2 my_pkg-1.2.3

Via API:

.. code-block:: python

   >>> from rez.package_copy import copy_package
   >>> from rez.packages import get_latest_package
   >>>
   >>> p = get_latest_package("python")
   >>> p
   Package(FileSystemPackageResource({'location': '/home/ajohns/packages', 'name': 'python', 'repository_type': 'filesystem', 'version': '3.7.4'}))
   >>>
   >>> r = copy_package(p, "./repo2")
   >>>
   >>> print(pprint.pformat(r))
   {
      'copied': [
         (
               Variant(FileSystemVariantResource({'location': '/home/ajohns/packages', 'name': 'python', 'repository_type': 'filesystem', 'index': 0, 'version': '3.7.4'})),
               Variant(FileSystemVariantResource({'location': '/home/ajohns/repo2', 'name': 'python', 'repository_type': 'filesystem', 'index': 0, 'version': '3.7.4'}))
         )
      ],
      'skipped': []
   }

Copying packages is actually done one variant at a time, and you can copy some
variants of a package if you want, rather than the entire package. The API call's
return value shows what variants were copied. The 2-tuple in ``copied`` lists the
source (the variant that was copied from) and destination (the variant that was
created) respectively.

.. danger::
   Do not simply copy package directories on disk.
   You should always use :ref:`rez-cp` or use the API. Copying directly on disk is bypassing rez and
   this can cause problems such as a stale resolve cache. Using :ref:`rez-cp` and the API give
   you more control anyway.

.. _enabling-package-copying:

Enabling Package Copying
------------------------

Copying packages is enabled by default, however you're also able to specify which
packages are and are not *relocatable*, for much the same reasons as given
:ref:`here <enabling-package-caching>`.

You can mark a package as non-relocatable by setting :attr:`relocatable`
to ``False`` in its package definition file. There are also config settings that affect relocatability
in the event that relocatable is not defined in a package's definition. For example,
see :data:`default_relocatable`, :data:`default_relocatable_per_package`
and :data:`default_relocatable_per_repository`.

Attempting to copy a non-relocatable package will raise a :exc:`~rez.exceptions.PackageCopyError`.
However, note that there is a ``force`` option that will override this. Use at
your own risk.

.. _moving-packages:

Moving Packages
===============

Packages can be moved from one :ref:`package repository <package-repositories-concept>`
to another. Be aware that moving a package does not actually delete the source
package however. Instead, the source package is hidden (ignored). It is up to
you to delete it at some later date.

To move a package via commandline:

.. code-block:: console

   $ rez-mv --dest-path /packages2 python-3.7.4 /packages

Via API:

.. code-block:: python

   >>> from rez.package_move import move_package
   >>> from rez.packages import get_package_from_repository
   >>>
   >>> p = get_package_from_repository("python", "3.7.4", "/packages")
   >>> p
   Package(FileSystemPackageResource({'location': '/packages', 'name': 'python', 'repository_type': 'filesystem', 'version': '3.7.4'}))
   >>>
   >>> new_p = move_package(p, "/packages2")
   >>> new_p
   Package(FileSystemPackageResource({'location': '/packages2', 'name': 'python', 'repository_type': 'filesystem', 'version': '3.7.4'}))
   >>>
   >>> p = get_package_from_repository("python", "3.7.4", "/packages")
   >>> p
   None

Be aware that a non-relocatable package is also not movable (see
:attr:`here <relocatable>`. Like package
copying, there is a ``force`` option to move it regardless.

A typical reason you might want to move a package is to archive packages that are
no longer in use. In this scenario, you would move the package to some archival
package repository. In case an old runtime needs to be resurrected, you would add
this archival repository to the packages path before performing the resolve.

.. note::
   You will probably want to use the :option:`--keep-timestamp <rez-mv --keep-timestamp>` option when doing this,
   otherwise rez will think the package did not exist prior to its archival date.

.. _removing-packages:

Removing Packages
=================

Packages can be removed. This is different from ignoring. The package and its
payload is deleted from storage, whereas ignoring just hides it. It is not
possible to un-remove a package.

To remove a package via commandline:

.. code-block:: console

   $ rez-rm --package python-3.7.4 /packages

Via API:

.. code-block:: python

   >>> from rez.package_remove import remove_package
   >>>
   >>> remove_package("python", "3.7.4", "/packages")

During the removal process, package versions will first be ignored so that
partially-deleted versions are not visible.

It can be useful to ignore packages that you don't want to use anymore, and
actually remove them at a later date. This gives you a safety buffer in case
current runtimes are using the package. They won't be affected if the package is
ignored, but could break if it is removed.

To facilitate this workflow, :ref:`rez-rm` lets you remove all packages that have
been ignored for longer than N days (using the timestamp of the
:file:`.ignore{{version}}` file). Here we remove all packages that have been ignored
for 30 days or longer:

.. code-block:: console

   $ rez-rm --ignored-since=30 -v
   14:47:09 INFO     Searching filesystem@/home/ajohns/packages...
   14:47:09 INFO     Removed python-3.7.4 from filesystem@/home/ajohns/packages
   1 packages were removed.

Via API:

.. code-block:: python

   >>> from rez.package_remove import remove_packages_ignored_since
   >>>
   >>> remove_packages_ignored_since(days=30)
   1
