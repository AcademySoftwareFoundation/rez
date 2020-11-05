This folder contains all the libraries on which rez depends to run.

Libraries that are required to install Rez can be found in [src/build_utils](../../build_utils).

The dependencies list found here is used to track which version we use so that when we
revisit the install procedure, it will be much simpler to do any change in the vendored
libraries (updating them, un-vendoring some, etc).

Note that the latest versions column is just to give us an idea of how far back we are.


# Vendored Packages

<table>
<tr>
<th>Package</th>
<th>Version</th>
<th>Latest</th>
<th>Note</th>
</tr>

<!-- ######################################################### -->
<tr><td>
    amqp
</td><td>
    1.4.9 (Jan 8, 2016)
</td><td>
    2.4.2 (Mar 3, 2019)
</td><td>
    -
</td></tr>

<!-- ######################################################### -->
<tr><td>
    argcomplete
</td><td>
    ?
</td><td>
    1.9.5 (Apr 2, 2019)
</td><td>
    Our version seems patched.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    atomicwrites
</td><td>
    1.2.1 (Aug 30, 2018)
</td><td>
    1.3.0 (Feb 1, 2019)
</td><td>
    -
</td></tr>

<!-- ######################################################### -->
<tr><td>
    attrs
</td><td>
    19.1.0 (Mar 3, 2019)
</td><td>
    19.1.0 (Mar 3, 2019)
</td><td>
    Added (July 2019) to enable the use of packaging lib that depends on it.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    colorama
</td><td>
    0.4.1 (Nov 25, 2018)
</td><td>
    0.4.1 (Nov 25, 2018)
</td><td>
    -
</td></tr>

<!-- ######################################################### -->
<tr><td>
    distlib
</td><td>
    0.2.9.post0 (May 14, 2019)
</td><td>
    0.3.0 (No official release yet)
</td><td>
    Updated (June 2019) to enable wheel distribution based installations.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    distro
</td><td>
    1.5.0 (Mar 31, 2020)
</td><td>
    1.5.0 (Mar 31, 2020)
</td><td>
-
</td></tr>

<!-- ######################################################### -->
<tr><td>
    enum
</td><td>
    ?
</td><td>
    ?
</td><td>
    By looking at the code, it's probably enum34. If so, the latest version is
    1.1.6 (May 15, 2016)
</td></tr>

<!-- ######################################################### -->
<tr><td>
    lockfile
</td><td>
    0.9.1 (Sep 19, 2010)
</td><td>
    0.12.2 (Nov 25, 2015)
</td><td>
    -
</td></tr>

<!-- ######################################################### -->
<tr><td>
    memcache (python-memcached)
</td><td>
    1.59 (Dec 15, 2017)
</td><td>
    1.59 (Dec 15, 2017)
</td><td>
    We could try to move to a more maintained package like pymemcache from
    pinterest. NOTE: A port to redis may be a better option, people are more
    familiar with it and it already has a good python client that supports conn
    pooling.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    packaging
</td><td>
    19.0 (Jan 20, 2019)
</td><td>
    19.0 (Jan 20, 2019)
</td><td>
    Added (July 2019) to enable PEP440 compatible versions handling.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    progress
</td><td>
    1.5 (Mar 6, 2019)
</td><td>
    1.5 (Mar 6, 2019)
</td><td>
    Upgraded from 1.2 to 1.5 as of Oct 16 2019
</td></tr>

<!-- ######################################################### -->
<tr><td>
    pydot
</td><td>
    1.4.2.dev0 (Oct 28, 2020)
</td><td>
    1.4.2.dev0 (Oct 28, 2020)
</td><td>
    
* Updated (July 2019) in order to update pyparsing lib which in turn is
required by the packaging library. Updated (Aug 2019) for py3.

* Updated (Nov 2020) for finding right dot executable on Windows + Anaconda, see [pydot/pydot#205](https://github.com/pydot/pydot/issues/205) for detail. Also, pydot has not bumping version for a long time, log down commit change here: a10ced4 -> 03533f3
</td></tr>

<!-- ######################################################### -->
<tr><td>
    pygraph (python-graph-core)
</td><td>
    1.8.2 (Jul 14, 2012)
</td><td>
    1.8.2 (Jul 14, 2012)
</td><td>
    -
</td></tr>

<!-- ######################################################### -->
<tr><td>
    pyparsing
</td><td>
    2.4.0 (Apr 8, 2019)
</td><td>
    2.4.0 (Apr 8, 2019)
</td><td>
    Updated (July 2019) along with pydot to allow for packaging lib to be used.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    schema
</td><td>
    0.3.1 (Apr 28, 2014)
</td><td>
    0.7.0 (Feb 27, 2019)
</td><td>
    Our version is patched.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    six
</td><td>
    1.12.0 (Dec 9, 2018)
</td><td>
    1.12.0 (Dec 9, 2018)
</td><td>
    Updated (July 2019) to coincide with packaging lib addition that depends on.
    Also now required to support py2/3 interoperability.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    sortedcontainers
</td><td>
    1.5.7 (Dec 22, 2016)
</td><td>
    2.1.0 (Mar 5, 2019)
</td><td>
    Used in the resolver. Updating would possibly give us some speed improvements.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    yaml lib (PyYAML)
</td><td>
    5.1 (May 30, 2011)
</td><td>
    5.1.2  (Jul 5, 2018)
</td><td>
    No changes but must maintain separate version between py2 and py3 for time being.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    yaml lib3 (PyYAML)
</td><td>
    5.1 (May 30, 2011)
</td><td>
    5.1.2  (Jul 31, 2018)
</td><td>
    No changes but must maintain separate version between py2 and py3 for time being.
</td></tr>

<!-- ######################################################### -->
<tr><td>
    version
</td><td>
    -
</td><td>
    -
</td><td>
    Part of rez (TODO: Mve out of vendor).
</td></tr>

</table>
