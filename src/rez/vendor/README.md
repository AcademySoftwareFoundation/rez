
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
3.1.2 (Sep 16, 2023)
</td><td>
Apache 2.0
</td><td>
https://github.com/kislyuk/argcomplete<br>
Updated (Sept 2025)
</td></tr>

<!-- ######################################################### -->
<tr><td>
atomicwrites
</td><td>
1.4.1 (Jul 8, 2022)
</td><td>
MIT
</td><td>
https://github.com/untitaker/python-atomicwrites<br>
No changes.<br>
Updated (April 2025) to help address py3.12 update.
</td></tr>

<!-- ######################################################### -->
<tr><td>
colorama
</td><td>
0.4.6 (Oct 24, 2022)
</td><td>
BSD 3-Clause
</td><td>
https://github.com/tartley/colorama<br>
No changes.<br>
Updated (April 2025) to help address py3.12 update.
</td></tr>

<!-- ######################################################### -->
<tr><td>
distlib
</td><td>
0.3.9 (Oct 29, 2024)
</td><td>
PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
</td><td>
https://bitbucket.org/pypa/distlib/src/master/<br>
Updated (April 2025) to help address py3.12 update.
</td></tr>

<!-- ######################################################### -->
<tr><td>
distro
</td><td>
1.9.0 (Dec 24, 2023)
</td><td>
Apache 2.0
</td><td>
https://github.com/python-distro/distro<br>
No changes.<br>
Updated (April 2025) to help address py3.12 update.
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
importlib-metadata
</td><td>
6.7.0
</td><td>
Apache 2.0
</td><td>
https://pypi.org/project/importlib-metadata/<br>
Pinned to 6.7.0 to support Python 3.7. This dependency can be dropped once we drop support for Python 3.7.
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
1.2.0 (Feb 5, 2021)
</td><td>
BSD 3-Clause
</td><td>
https://github.com/pika/pika
</td></tr>


<!-- ######################################################### -->
<tr><td>
progress
</td><td>
1.6 (July 28, 2021)
</td><td>
ISC
</td><td>
https://github.com/verigak/progress<br>
No changes.<br>
Updated (April 2025) to help address py3.12 update.
</td></tr>

<!-- ######################################################### -->
<tr><td>
pydot
</td><td>
2.0.0 (Dec 30, 2023)
</td><td>
MIT
</td><td>
https://github.com/pydot/pydot<br>
Updated (Sept 2025)
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
3.1.4 (Aug 25, 2024)
</td><td>
MIT
</td><td>
https://github.com/pyparsing/pyparsing<br>
Updated (Sept 2025)
</td></tr>

<!-- ######################################################### -->
<tr><td>
schema
</td><td>
0.3.1 (Apr 28, 2014) (https://github.com/keleshev/schema/blob/916ba05e22b7b370b3586f97c40695e7b9e7fe33)
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
1.17.0 (Dec 4, 2024)
</td><td>
MIT
</td><td>
https://github.com/benjaminp/six<br>
Updated (April 2025) to help address py3.12 update.<br>
No longer needed in rez itself, but still used by other vendored modules.
</td></tr>

<!-- ######################################################### -->
<tr><td>
typing_extensions
</td><td>
4.7.1
</td><td>
PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
</td><td>
https://pypi.org/project/zipp/<br>
Dependency for importlib-metadata. Can be dropped once we drop support for Python 3.7.
</td></tr>

<!-- ######################################################### -->
<tr><td>
yaml (PyYAML)

</td><td>
6.0.1 (July 17, 2023)
</td><td>
MIT
</td><td>
https://github.com/yaml/pyyaml<br>
No changes. Bounded to 6.0.1 by current py3.7.<br>
Updated (April 2025) to help address py3.12 update.
</td></tr>

<!-- ######################################################### -->
<tr><td>
zipp
</td><td>
3.15.0
</td><td>
MIT
</td><td>
https://pypi.org/project/zipp/<br>
Dependency for importlib-metadata. Can be dropped once we drop support for Python 3.7.
</td></tr>

</table>
