================
Package Orderers
================

Rez's default :ref:`version <versions-concept>` resolution algorithm will always sort by the latest alphanumeric
version. However, package orderers allow you to customize this functionality globally,
or at a per package level.

This can be used to ensure that specific version have priority over others.
Higher versions can still be accessed if explicitly requested.

Configuration
=============

Package orderers can be configured in the ``rezconfig.py`` via the :data:`package_orderers` setting.

Types
=====

These are the available built-in orderers.

sorted
------

This is the default orderer that sorts based on the package's :attr:`version` attribute.

You can optionally explicitly request this orderer like this:

.. code-block:: python

    package_orderers = [
        {
            "type": "sorted", # Required
            "descending": True, # Required
            "packages": ["python"] # Optional, if not supplied, orderer applies to all packages
        }
    ]

version_split
-------------

This orderer orders all package versions less than or equal to a given version first, then sorts by the default
sorted order.

For example, given the versions [5, 4, 3, 2, 1], an orderer initialized with version=3 would give the
order [3, 2, 1, 5, 4].

.. code-block:: python

    package_orderers = [
        {
           "type": "version_split",
           "first_version": "2.7.16"
        }
    ]


A common use case is to ease migration from python-2 to python-3:

.. code-block:: python

   package_orderers = [
       {
          "type": "per_family",
          "orderers": [
               {
                   "packages": ["python"],
                   "type": "version_split",
                   "first_version": "2.7.16"
               }
           ]
       }
   ]

This will ensure that for the "python" package, versions equals or lower than "2.7.16" will have priority.
Considering the following versions: "2.7.4", "2.7.16", "3.7.4":

.. table::
   :align: left

   ==================== =============
   Example              Result
   ==================== =============
   rez-env python       python-2.7.16
   rez-env python-3     python-3.7.4
   ==================== =============

Package orderers will also apply to variants of packages.
Consider a package "pipeline-1.0" which has the following variants:
``[["python-2.7.4", "python-2.7.16", "python-3.7.4"]]``

.. table::
   :align: left

   ============================= ==========================
   Example                       Result
   ============================= ==========================
   rez-env pipeline              pipeline-1.0 python-2.7.16
   rez-env pipeline python-3     pipeline-1.0 python-3.7.4
   ============================= ==========================


per_family
----------

This orderer allows you to define different orderers to different package families.

.. code-block:: python

    package_orderers = [
        {
           "type": "per_family",
           "orderers": [
                {
                    "packages": ["python"],
                    "type": "version_split",
                    "first_version": "2.7.16"
                }
            ]
        }
    ]


soft_timestamp
--------------

This orderer takes in a given time ``T`` and returns packages released before ``T``, in descending order, followed by
those released after.

If ``rank`` is non-zero, version changes at that rank and above are allowed over the timestamp.

A timestamp can be generated with python:

.. code-block:: text

   $ python -c "import datetime, time; print(int(time.mktime(datetime.date(2019, 9, 9).timetuple())))"
   1568001600

The following example will prefer package released before 2019-09-09.

.. code-block:: python

   package_orderers = [
       {
           "type": "soft_timestamp",
           "timestamp": 1568001600,  # 2019-09-09
           "rank": 3
       }
   ]

The rank can be used to allow some versions released after the timestamp to still be considered.
When using semantic versionnng, a value of 3 is the most common.
This will let version with a different patch number to be accepted.

Considering a package "foo" with the following versions:

- "1.0.0" was released at 2019-09-07
- "2.0.0" was released at 2019-09-08
- "2.0.1" was released at 2019-09-10
- "2.1.0" was released at 2019-09-11
- "3.0.0" was released at 2019-09-12

the following talbes shows the effect of rank:

.. table::
   :align: left

   =========== ========== ==== =========
   Example     Timestamp  Rank Result
   =========== ========== ==== =========
   rez-env foo 2019-09-09 0    foo-2.0.0
   rez-env foo 2019-09-09 3    foo-2.0.1
   rez-env foo 2019-09-09 2    foo-2.1.0
   rez-env foo 2019-09-09 1    foo-3.0.0
   =========== ========== ==== =========


no_order
--------

An orderer that does not change the order - a no op.

This orderer is useful in cases where you want to apply some default orderer
to a set of packages, but may want to explicitly NOT reorder a particular
package. You would use a :class:`rez.package_order.NullPackageOrder` in a :class:`rez.package_order.PerFamilyOrder` to do this.


Custom orderers
===============

It is possible to create custom orderers using the API. This can be achieved
by subclassing :class:`rez.package_order.PackageOrder` and implementing some mandatory
methods. Once that's done, you need to register the orderer using :func:`rez.package_order.register_orderer`.

.. note::

   Implementing a custom orderer should only be done if absolutely necessary.
   It could make your environment behave in very special ways and more importantly
   in non expected ways from a user perspective. It can also make it harder to share
   the set of affected packages to others.


.. code-block:: python
   :caption: rezconfig.py

   from rez.version import Version
   from rez.package_order import PackageOrder, register_orderer


   class MyOrderer(PackageOrder):
       name = "my_orderer"

       def __init__(self, custom_arg: str, **kwargs):
           super().__init__(self, **kwargs)
           self.custom_arg = custom_arg

       def sort_key_implementation(self, package_name: str, version: Version):
           pass

       def __str__(self):
           pass

       def __eq__(self, other):
           pass

       def to_pod(self, other):
           pass

       @classmethod
       def from_pod(cls, data):
           pass


   register_orderer(MyOrderer)

   package_orderers = [
       {
           "type": "my_orderer",
           "custom_arg": "value here"
       }
   ]

For more details, please see :gh-rez:`src/rez/package_order.py`.
