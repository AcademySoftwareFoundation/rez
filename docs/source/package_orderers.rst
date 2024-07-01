================
Package Orderers
================

Rez's default :ref:`version <versions-concept>` resolution algorithm will always sort by the latest alphanumeric
version. However, package orderers allow you to customize this functionality globally,
or at a per package level.

Configuring package orderers
============================

Package ordering settings are not configured in each package's ``package.py``. Instead they are configured in the
``rezconfig.py`` via the :data:`package_orderers` setting.

Sorted Order
------------

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

Per Family Order
----------------

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

Version Split Package Order
---------------------------

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

Timestamp Package Order
-----------------------

This orderer takes in a given time ``T`` and returns packages released before ``T``, in descending order, followed by
those released after.

If ``rank`` is non-zero, version changes at that rank and above are allowed over the timestamp.

.. code-block:: python

    package_orderers = [
        {
            "type": "soft_timestamp",
            "timestamp": 1568001600,  # 2019-09-09
            "rank": 3
        }
    ]