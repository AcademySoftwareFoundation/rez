=======
Rez GUI
=======

Rez GUI can be used to provide a graphical interface to non-technical artists in your studio.

To start, you will need to install either PySide or PyQt. The easiest way to do this is to use
another Rez command :ref:`rez-pip`.

.. note::
   PySide2 is not pip installable for Python 3.7+. Therefore we will install the newer PySide6.

PySide6 does not install correctly with the `rez-pip` that is included with rez. Therefore,
you will need to install the new `rez-pip` from `here <https://github.com/JeanChristopheMorinPerso/rez-pip.git>`_

To install PySide6 with the new `rez-pip` on the commandline:

.. code-block:: console

   $ rez-pip2 PySide6

This will create a PySide6 rez package that has a dependency on a python package of the same
version that rez-pip detected.

NOTE: rez-pip cannot create a functioning PySide6 rez package. You must use the new rez-pip.

Next, we will use `rez-bind` to create the `python` package that PySide6 depends on:

.. code-block:: console

   $ rez-bind python

.. warning::
    Attempting to rez-bind python on Windows is broken and is a known
    `issue <https://github.com/AcademySoftwareFoundation/rez/issues/594/>`_.

    As a workaround, we recommend using
    `this <https://github.com/techartorg/rez_utils/tree/main/rezify_python>`_
    rewritten python package whose build command can use `winget` to download
    Python at build time.

Before we can do that, we need to convert
`rez-gui` into a rez package itself. We can do this with this commandline:

.. code-block:: console

   $ rez-bind rezgui --gui-lib PySide6
