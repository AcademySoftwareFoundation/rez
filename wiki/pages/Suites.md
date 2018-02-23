## Overview

Let us say that you wish to provide a number of different tools to your users,
even though these tools may require being run in different environments. For
example, you may want artists at your studio to be able to run *maya* and *nuke*
from the command line, without needing to know that they execute within different
environments.

Let's say that in order to do this, you create two *contexts* - *maya.rxt* and
*nuke.rxt* (see [here](Contexts#baking-resolves) for more information). In
order to run maya, you would do this:

    ]$ rez-env --input maya.rxt -- maya

You may then decide to wrap this command within a wrapper script which is also
called *maya*, and that might look something like this:

    #!/bin/bash
    rez-env --input maya.rxt -- maya $*

Now, if you put this somewhere on *$PATH*, and do the same for *nuke*, then
voila, your artists can run these applications from the command line, without
needing to know what's happening under the hood.

This, in a nutshell, is what a *suite* does. A suite is simply a directory
containing a set of contexts, and wrapper scripts which run tools within those
contexts.

## The rez-suite Tool

Let's go through the same example, this time using the *rez-suite* tool.

First, we create the suite. This creates a directory called *mysuite* in the
current working directory:

    ]$ rez-suite --create mysuite

Now we need to add contexts to our suite. First we create the contexts:

    ]$ rez-env maya-2016.2 --output maya.rxt
    ]$ rez-env nuke --output nuke.rxt

Then, we add these contexts to the suite (note that the *--context* arg just
gives each context a label - you would typically have this match the context
filename as shown).

    ]$ rez-suite --add maya.rxt --context maya mysuite
    ]$ rez-suite --add nuke.rxt --context nuke mysuite

The suite is created! Now all we need to do is to activate it, and that's as
simple as adding its *bin* path to *$PATH*:

    ]$ export PATH=$(pwd)/mysuite/bin:$PATH

You should now see your tools coming from the suite:

    ]$ which maya
    ./mysuite/bin/maya

    ]$ ls ./mysuite/bin
    maya
    nuke

## Suite Tools

The tools in a context which are exposed by the suite is determined by the
[tools](Package-Definition-Guide#tools) package attribute. For example, the
*maya* package might have a *tools* definition like so:

    # in maya package.py
    tools = [
        "maya",
        "mayapy",
        "fcheck"
    ]

All these tools would be made available in the suite (although you can explicitly
hide tools - see the *rez-suite* *--hide* option).

> [[media/icons/warning.png]] Only packages listed in the context *requests*,
> that are not weak or conflict requests, have their tools exposed - packages
> pulled in as dependencies do not. If you need to control the version of a package
> not in the request, without adding its command line tools, just add it as a weak
> reference to the request list.

### Tool Aliasing

Tools can be aliased to different names, either explicitly (on a per-tool basis),
or by applying a common prefix or suffix to all tools in a context.

Prefixing/suffixing is particularly useful when you want to expose the same
package's tools, but in two or more contexts. For example, you may want to run a
stable version of maya, but also a newer beta version. These would run in
different contexts, and the beta context might prefix all tools with *_beta*,
hence making available tools such as *maya_beta*.

For example, here we create a context with a newer version of maya, add it to
the suite, then add a suffix to all its tools:

    ]$ rez-env maya-2017 --output maya2017.rxt
    ]$ rez-suite --add maya2017.rxt --context maya2017 mysuite
    ]$ rez-suite --suffix _beta --context maya2017 mysuite

### Control Arguments

When using suite tools, any arguments passed to the wrappers are passed through
to the underlying tool, as expected. However, there is an exception to the case -
rez provides a set of *control* arguments, which are prefixed with `+`/`++`
rather than the typical `-`/`--`. These are suite-aware arguments that pass
directly to rez. You can get a listing of them using `+h`/`++help`, like so:

```
]$ maya ++help
usage: maya [+h] [+a] [+i] [+p [PKG [PKG ...]]] [++versions]
            [++command COMMAND [ARG ...]] [++stdin] [++strict] [++nl]
            [++peek] [++verbose] [++quiet] [++no-rez-args]

optional arguments:
  +h, ++help            show this help message and exit
  +a, ++about           print information about the tool
  +i, ++interactive     launch an interactive shell within the tool's
                        configured environment
  +p [PKG [PKG ...]], ++patch [PKG [PKG ...]]
                        run the tool in a patched environment
  ++versions            list versions of package providing this tool
  ++command COMMAND [ARG ...]
                        read commands from string, rather than executing the
                        tool
  ++stdin               read commands from standard input, rather than
                        executing the tool
  ++strict              strict patching. Ignored if ++patch is not present
  ++nl, ++no-local      don't load local packages when patching
  ++peek                diff against the tool's context and a re-resolved copy
                        - this shows how 'stale' the context is
  ++verbose             verbose mode, repeat for more verbosity
  ++quiet               hide welcome message when entering interactive mode
  ++no-rez-args         pass all args to the tool, even if they start with '+'
```

For example, to see information about the suite wrapper:

    ]$ maya ++about
    Tool:     maya
    Path:     ./mysuite/bin/maya
    Suite:    ./mysuite
    Context:  ./mysuite/contexts/maya2016.rxt ('maya2016')

> [[media/icons/info.png]] If the target tool also uses `+` for some of its
> own arguments, you can change the prefix character that rez uses for its
> control arguments. See the *rez-suite* *--prefix-char* option.
