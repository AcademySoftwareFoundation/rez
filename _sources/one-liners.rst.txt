One-Liners
==========

A list of useful one-liners for rez-config and related tools

Display info about the package foo:

::

    rez-info foo

List the packages that foo depends on:

::

    rez-config --print-packages foo

Jump into an environment containing foo-5(.x.x.x...):

::

    rez-env foo-5

Run a command inside a configured shell

::

    rez-run foo-5 bah-1.2 -- my-command

Show the resolve dot-graph for a given shell:

::

    rez-run foo-5 bah-1.2 fee -- rez-context-image

Display a dot-graph showing the first failed attempt of the given configuration PKGS:

::

    rez-config --max-fails=0 --dot-file=/tmp/dot.jpg PKGS ; firefox /tmp/dot.jpg

Show a dot-graph of all the packages dependent on foo:

::

    rez-depends show-dot foo

List every package in the system, and the description of each

::

    rez-config-list --desc

Show the resolve dot-graph for a given shell, but just show that part of the graph that
contains packages dependent (directly or indirectly) on fee:

::

    rez-run foo-5 bah-1.2 fee -- rez-context-image --package=fee

Run a command inside a toolchain wrapper:
::

    rez-run mytoolchain -- sometool -- some-command

Jump into a toolchain, and then into a wrapper's env:

::

    rez-run mytoolchain
    sometool ---i
