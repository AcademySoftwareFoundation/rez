
Overview
--------------------------------------------------------------------------------

This is a repository of package installers. Each directory contains a rez
project that you can build (using rez-build) or release (using rez-release).
Doing so will build or release the associated software (gcc, boost etc) as a
rez package. See the following 'Quick Start Guide' for more details.

Please note that this project repository is for reference only. You should copy
them into your own repo - at that point you can set the correct versions, put a
requirement on your operating system of choice, and so on.

These installer packages make heavy use of the 'ExternalProject_add' CMake macro.
You can modify calls to this macro in the CMakeLists.txt to do things such as
apply your own patches. You would include these patches in your own package
repository so that you retain a change history of them.

Once you have these installer packages in your own repo (or repos) you will be
able to rez-build and rez-release them. You can keep them all within a single
repo, or split them out into separate repos, the choice is yours and both will
work.

The following environment variables are used by some packages:

REZ_REPO_PAYLOAD_DIR: Path to where package downloads (such as tgz files) are
	stored. Source disappears online and security measures often mean it is
	difficult to install from URL within a studio, so we opt to install from
	already downloaded source, rather than downloading as part of the install.


Quick Start Guide
--------------------------------------------------------------------------------

1) Copy contents of ./repository to another location;

2) Optionally (if you want to release packages) put this copy under version control;

3) Cd into a package you would like to install (eg hello_world_py/1.0.0);

4) Make any necessary changes to the package.py and/or CMakeLists.txt file. A
   package's definition and/or build process will often not be exactly what a
   studio wants.

5) Run:

   ]$ rez-build -i

   This will build the package, and install it to your local packages path,
   typically ~/packages.

5.1) You often need to provide the source archive that the packages is built
   from. Rez looks for such archives under the path set by the environment
   variable REZ_REPO_PAYLOAD_DIR. If not set, an error message will tell you.
   Set this variable and goto the next step.

5.2) If the source archive you need is not present under REZ_REPO_PAYLOAD_DIR,
   an error message will tell you so. Download the archive from the suggested
   URL, and goto the next step.

6) Test:

   ]$ rez-env hello_world_py
   ]$ hello
   Hello world!

7) Once your local install is working, you may want to release the package so
   the whole studio can use it. To release:

   ]$ rez-release

8) That's it. To install newer versions, download the newer source archives,
   update package.py/CMakeLists.txt appropriately, and rez-release once more.
   All changes to your installer scripts are now kept in rez packages, and are
   under source control.
