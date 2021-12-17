
Rez contains a set of embedded dependencies, listed in the table below. The reason
they're embedded into the project is because rez itself is often used as a rez
package, which means its dependencies would need to be rez packages also. Were these
to be sourced from pip, we would need to convert them from pip packages into rez
packages. This is doable (via the `rez-pip` tool and API) but represents a
significantly larger barrier of entry to installation.

Embedding requirements like this is not ideal however, and a move to external
requirements is not off the cards. We would need to update the process for
installing rez as a rez package (currently done via `install.py -p`), and ensure
that the rez-to-pip conversion process for its dependencies is seamless and well
tested.


# Vendored Packages

<table>
<tr>
<th>Package</th>
<th>Version</th>
<th>License</th>
<th>Note</th>
</tr>

<!-- ######################################################### -->
<tr><td>
argcomplete
</td><td>
?
</td><td>
Apache 2.0
</td><td>
https://github.com/kislyuk/argcomplete<br>
Our version seems patched.
</td></tr>

<!-- ######################################################### -->
<tr><td>
atomicwrites
</td><td>
1.2.1 (Aug 30, 2018)
</td><td>
MIT
</td><td>
https://github.com/untitaker/python-atomicwrites
</td></tr>

<!-- ######################################################### -->
<tr><td>
attrs
</td><td>
19.1.0 (Mar 3, 2019)
</td><td>
MIT
</td><td>
https://github.com/python-attrs/attrs<br>
Added (July 2019) to enable the use of packaging lib that depends on it.
</td></tr>

<!-- ######################################################### -->
<tr><td>
colorama
</td><td>
0.4.1 (Nov 25, 2018)
</td><td>
BSD 3-Clause
</td><td>
https://github.com/tartley/colorama<br>
</td></tr>

<!-- ######################################################### -->
<tr><td>
distlib
</td><td>
0.2.9.post0 (May 14, 2019)
</td><td>
PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
</td><td>
https://bitbucket.org/pypa/distlib/src/master/<br>
Updated (June 2019) to enable wheel distribution based installations.
</td></tr>

<!-- ######################################################### -->
<tr><td>
distro
</td><td>
1.5.0 (Mar 31, 2020)
</td><td>
Apache 2.0
</td><td>
https://github.com/python-distro/distro
</td></tr>

<!-- ######################################################### -->
<tr><td>
enum
</td><td>
?
</td><td>
BSD
</td><td>
https://pypi.org/project/enum34/<br>
By looking at the code, it's probably enum34. If so, the latest version is
1.1.6 (May 15, 2016)
</td></tr>

<!-- ######################################################### -->
<tr><td>
lockfile
</td><td>
0.9.1 (Sep 19, 2010)
</td><td>
MIT
</td><td>
https://github.com/openstack-archive/pylockfile<br>
Deprecated project, recommends upgrading to
https://github.com/harlowja/fasteners
</td></tr>

<!-- ######################################################### -->
<tr><td>
memcache (python-memcached)
</td><td>
1.59 (Dec 15, 2017)
</td><td>
PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
</td><td>
https://github.com/linsomniac/python-memcached<br>
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
Duel license, Apache 2.0, BSD 2-Clause
</td><td>
https://github.com/pypa/packaging<br>
Added (July 2019) to enable PEP440 compatible versions handling.
</td></tr>

<!-- ######################################################### -->
<tr><td>
pika
</td><td>
1.2.0
</td><td>
BSD 3-Clause
</td><td>
https://github.com/pika/pika
</td></tr>


<!-- ######################################################### -->
<tr><td>
progress
</td><td>
1.5 (Mar 6, 2019)
</td><td>
ISC
</td><td>
https://github.com/verigak/progress<br>
Upgraded from 1.2 to 1.5 as of Oct 16 2019
</td></tr>

<!-- ######################################################### -->
<tr><td>
pydot
</td><td>
1.4.2.dev0 (Oct 28, 2020)
</td><td>
MIT
</td><td>
https://github.com/pydot/pydot<br>

* Updated (July 2019) in order to update pyparsing lib which in turn is
required by the packaging library. Updated (Aug 2019) for py3.
* Updated (Nov 2020) for finding right dot executable on Windows + Anaconda,
see [pydot/pydot#205](https://github.com/pydot/pydot/issues/205) for detail.
Also, pydot has not bumping version for a long time, log down commit change
here: a10ced4 -> 03533f3
</td></tr>

<!-- ######################################################### -->
<tr><td>
pygraph (python-graph-core)
</td><td>
1.8.2 (Jul 14, 2012)
</td><td>
MIT
</td><td>
https://github.com/pmatiello/python-graph<br>
No longer maintained, moved to https://github.com/Shoobx/python-graph
</td></tr>

<!-- ######################################################### -->
<tr><td>
pyparsing
</td><td>
2.4.0 (Apr 8, 2019)
</td><td>
MIT
</td><td>
https://github.com/pyparsing/pyparsing<br>
Updated (July 2019) along with pydot to allow for packaging lib to be used.
</td></tr>

<!-- ######################################################### -->
<tr><td>
schema
</td><td>
0.3.1 (Apr 28, 2014)
</td><td>
MIT
</td><td>
https://github.com/keleshev/schema<br>
Our version is patched.
</td></tr>

<!-- ######################################################### -->
<tr><td>
six
</td><td>
1.12.0 (Dec 9, 2018)
</td><td>
MIT
</td><td>
https://github.com/benjaminp/six<br>
Updated (July 2019) to coincide with packaging lib addition that depends on.
Also now required to support py2/3 interoperability.
</td></tr>

<!-- ######################################################### -->
<tr><td>
yaml lib (PyYAML)
</td><td>
5.1 (May 30, 2011)
</td><td>
MIT
</td><td>
https://github.com/yaml/pyyaml<br>
No changes but must maintain separate version between py2 and py3 for time being.
</td></tr>

<!-- ######################################################### -->
<tr><td>
yaml lib3 (PyYAML)
</td><td>
5.1 (May 30, 2011)
</td><td>
MIT
</td><td>
https://github.com/yaml/pyyaml<br>
No changes but must maintain separate version between py2 and py3 for time being.
</td></tr>

</table>
