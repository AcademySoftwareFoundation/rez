================
Testing packages
================

This page describes how to write tests with Rez and the types of tests Rez
excels at. This guide will be somewhat detailed. If you're looking for a quick
summary of how Rez tests work, check out :attr:`tests`.

Building And Installing
=======================

If you'd like to follow along, check out the example Rez package here:

1. Go to your source Rez package

.. code-block:: sh

   $ cd {root}/example_packages/rez_test_example

Replace {root} with the root of the Rez git repository.

Here is the ``tests`` attribute, for those who prefer to only read this page:

.. code-block:: python

    tests = {
        "black_diff": {
            "command": "black --diff --check python tests",
            "requires": ["black"],
        },
        "black": {
            "command": "black python tests",
            "requires": ["black"],
            "run_on": "explicit",
        },
        "documentation": {
            "command": "sphinx-build -b html documentation/source documentation/build",
            "on_variants": {"value": ["python-3"], "type": "requires"},
            "requires": ["Sphinx"],
            "run_on": "pre_release",
        },
        "unittest": {
            "command": "python -m unittest discover",
            "on_variants": {"value": ["python"], "type": "requires"},
        },
    }

2a. Install dependencies for our example

.. code-block:: sh

    $ rez-bind python
    $ rez-bind python --exe which python3
    $ rez-pip --install Sphinx --python-version=3
    $ rez-pip --install black --python-version=3
    $ rez-pip --install six --python-version=2

.. warning::
    This rez_test_example package has dependencies.
    Make sure you install them at least once!

2b. Install the source package (by running rez-build)

Firstly, build ``rez_test_example``.

.. code-block:: sh

    $ rez-build --clean --install

.. warning::
    Before running rez-test, run rez-build so your package is up to date!

In order for ``rez-test`` to work, we must have an installed Rez package. And in
order to install the package, we must build the Rez package at least once. If
you later modify the package.py, be sure to re-build again to make sure your
installed Rez package is up to date with your latest changes.

Now you may run ``rez-test`` for rez_test_example in variety of different ways:

.. code-block:: sh

    $ rez-test rez_test_example  # <-- This runs all "default" tests
    $ rez-test rez_test_example unittest  # <-- Runs the test named "unittest"
    $ rez-test rez_test_example unittest black_diff  # <-- Runs "unittest" and "black_diff"

We'll explore these options and what they do in the sections below.

Unit Testing
============

To run the unit tests of rez_test_example, there's 2 ways:

.. note::
    The relevant part of the ``tests`` attribute is as follows:

.. code-block:: python

    "unittest": {
        "command": "python -m unittest discover",
        "on_variants": {"value": ["python"], "type": "requires"},
    },


.. code-block:: sh

    $ rez-test rez_test_example unittest  # <-- Run "unittest" and nothing else
    $ rez-test rez_test_example  # <-- Run all default tests, including "unittest"

The first method runs just the one Rez test, called "unittest". The other runs
every default test. If a test does not define a "run_on" key, it is considered
default. Notice how some (but not all) of our tests in ``rez_test_example`` do
define "run_on". We'll explain why in later sections.

Either way, once run, you should notice the test output will look something
like this:

.. code-block:: sh

    Test results:
    --------------------------------------------------------------------------------
    2 succeeded, 0 failed, 0 skipped

    Test      Status   Variant                                                          Description
    ----      ------   -------                                                          -----------
    unittest  success  /home/selecaoone/packages/rez_test_example/1.0.0/python-2/six-1  Test succeeded
    unittest  success  /home/selecaoone/packages/rez_test_example/1.0.0/python-3        Test succeeded

In the ``rez-test`` command, we specified only one test to run but it ran twice.
The reason is because of the included
``"on_variants": {"value": ["python"], "type": "requires"}`` part.

We asked Rez to run "unittest" on every variant of our package which includes
"python".  Both of our 2 variants include "python" and so the ``rez-test`` ran
"unittest" twice, once per variant. We can see the variant path in the output.

.. code-block:: python

    variants = [
        ["python-2", "six-1"],
        ["python-3"],
    ]

In short, you can use "on_variants" to tell Rez "please run this test on all /
some of my variants" without needing to make multiple tests. Or omit
"on_variants" to have a test only run once, on-request.

Linting / Auto-Formatting
=========================

Another common use-case for ``rez-test`` is
`Code Linting <https://en.wikipedia.org/wiki/Lint_\(software\)>`_.
It's fairly common for Rez packages to have many linting related tests and
makes Rez packages much less prone to error. Typical examples of Python linters
and auto-formatters are:

- `black <https://pypi.org/project/black>`_
- `isort <https://pypi.org/project/isort>`_
- `pydocstyle <https://pypi.org/project/pydocstyle>`_
- `pylint <https://pypi.org/project/pylint>`_

And more.

In ``rez_test_example``, we've implemented the auto-formatter "black" as 2 Rez
test commands.

.. note::
    The relevant part of the ``tests`` attribute is as follows:

.. code-block:: python

    "black_diff": {
        "command": "black --diff --check python tests",
        "requires": ["black"],
    },
    "black": {
        "command": "black python tests",
        "requires": ["black"],
        "run_on": "explicit",
    },

"black_diff" checks the package for issues and reports them to the user if any
are found. "black", in contrast, actually make changes the user's files,
auto-formatting any of the issues found in "black_diff".

Because "black" modifies the user's file, we include ``"run_on": "explicit"``.
Recall that "explicit" means "only run this test when I ask you to". This means
running ``rez-test rez_test_example`` will not run "black", which is good because
the user may not appreciate their files being changed without being asked. But
they still have the option to use ``rez-test rez_test_example black`` to
auto-format their files whenever they want.

In contrast, "black_diff" does not modify any files and instead only reports
issues. So it's safe to run even by default. Because of that, "black_diff" does
not have ``"run_on": "explicit"`` defined.

General Commands
================

``rez-test`` is useful not just for running literal tests but also for executing
*tasks* of work. For example, ``rez-test`` can drive documentation automation.

.. note::
    The relevant part of the ``tests`` attribute is as follows:

.. code-block:: python

    "documentation": {
        "command": "sphinx-build -b html {root}/documentation/source {root}/build/documentation",
        "on_variants": {"value": ["python-3"], "type": "requires"},
        "requires": ["Sphinx"],
        "run_on": "pre_release",
    }

Here we have `Sphinx <https://www.sphinx-doc.org/en/master>`_ auto-generating
documentation, but only just before the Rez package is released (or if
explicitly asked for). The reason is simple - Sphinx can be slow to run and so
it isn't suitable to always run by default. But we do want to ensure that it
always runs as part of our release process, making `"run_on": "pre_release"` a
natural choice.

Parting Thoughts
================

As you can see, ``rez-test`` is very expressive and powerful. In just a few
lines, you can build unittests, CI workflows, and automation for your Rez
package in just a single ``tests`` attribute.

More Resources
==============

As mentioned at the start, there's :attr:`tests` if you wish to read more about
how "tests" is formatted and its features. There's also ``rez-test --help`` as
well as the `ASWF Slack board <https://slack.aswf.io>`_ where you can ask questions.

Happy ``rez-test``-ing!