#!/bin/bash
#
# Configuration script for rez.
#
# You need to run this before install.sh. It will attempt to find rez's dependencies, if
# it fails then you need to point it to the right binaries, directories etc.
#
# Once configuration succeeds, relevant info is written to ./rez.configured. You can then
# run install.sh
#
#

# Configuration settings. Either set them by hand here, or set the relevant REZCONFIG_XXX
# environment variables (see the following section) before invoking this script.
###---------------------------------------------------------------------------------------
### BEGIN EDITING HERE >>>
###---------------------------------------------------------------------------------------

# Path where you want to centrally deploy packages to (ie, a central location that all
# users can see). For example, /someserver/rez/packages
packages_path=

# Path to where you want to locally install packages to. Note the single quotes, which are
# needed to stop early substitution of $HOME.
local_packages_path='$HOME/packages'

# The system shell that rez expects to be running in. If left blank rez will identify
# Eg: bash, csh, tcsh
rezshell=

# The operating system. If left blank rez will identify. Eg: linux, windows, osx
osname=

# The operating system distribution. If left blank rez will identify
# Eg: Ubuntu-11.10
distro=
distro_version=

# The system architecture. If left blank rez will identify
# Eg: x86_64
sysarch=

# Binaries that rez needs, if left blank rez will try to find them
cmake_binary=
cpp_compiler_binary=
python_binary=

# Path to python modules, if left blank rez will try to find them. A common mistake is to
# include the trailing subdir (eg /.../.../yaml), that's one dir too many
pyyaml_path=
pydot_path=
pyparsing_path=
pymemcached_path=
pysvn_path=
gitpython_path=

# Your preferred text editor for writing package release notes. You can change this at any
# time by setting $REZ_RELEASE_EDITOR appropriately.
rez_release_editor=

# Your preferred image viewer, for viewing resolve graphs. You can change this at any time
# by setting $REZ_DOT_IMAGE_VIEWER appropriately.
rez_dot_image_viewer=

###---------------------------------------------------------------------------------------
### <<< END EDITING HERE
### DO NOT CHANGE ANYTHING PAST THIS LINE
###---------------------------------------------------------------------------------------

if [ "$packages_path" == "" ]; then
    packages_path=$REZCONFIG_PACKAGES_PATH
fi
if [ "$local_packages_path" == "" ]; then
    local_packages_path=$REZCONFIG_LOCAL_PACKAGES_PATH
fi
if [ "$rezshell" == "" ]; then
    rezshell=$REZCONFIG_SHELL
fi
if [ "$osname" == "" ]; then
    osname=$REZCONFIG_PLATFORM
fi
if [ "$distro" == "" ]; then
    distro=$REZCONFIG_DISTRO
fi
if [ "$distro_version" == "" ]; then
    distro_version=$REZCONFIG_DISTRO_VERSION
fi
if [ "$sysarch" == "" ]; then
    sysarch=$REZCONFIG_ARCH
fi
if [ "$cmake_binary" == "" ]; then
    cmake_binary=$REZCONFIG_CMAKE_BINARY
fi
if [ "$cpp_compiler_binary" == "" ]; then
    cpp_compiler_binary=$REZCONFIG_CPP_COMPILER_BINARY
fi
if [ "$python_binary" == "" ]; then
    python_binary=$REZCONFIG_PYTHON_BINARY
fi
if [ "$pyyaml_path" == "" ]; then
    pyyaml_path=$REZCONFIG_PYYAML_PATH
fi
if [ "$pydot_path" == "" ]; then
    pydot_path=$REZCONFIG_PYDOT_PATH
fi
if [ "$pyparsing_path" == "" ]; then
    pyparsing_path=$REZCONFIG_PYPARSING_PATH
fi
if [ "$pymemcached_path" == "" ]; then
    pymemcached_path=$REZCONFIG_PYMEMCACHED_PATH
fi
if [ "$pysvn_path" == "" ]; then
    pysvn_path=$REZCONFIG_PYSVN_PATH
fi
if [ "$gitpython_path" == "" ]; then
    gitpython_path=$REZCONFIG_GITPYTHON_PATH
fi

if [ "$rez_release_editor" == "" ]; then
    rez_release_editor=$REZCONFIG_RELEASE_EDITOR
fi
if [ "$rez_dot_image_viewer" == "" ]; then
    rez_dot_image_viewer=$REZCONFIG_DOT_IMAGE_VIEWER
fi


# cd into same dir as this script
absfpath=`[[ $0 == /* ]] && echo "$0" || echo "${PWD}/${0#./}"`
cwd=`dirname $absfpath`
cd $cwd


# usage
#-----------------------------------------------------------------------------------------
if [ "$1" == "--help" -o "$1" == "--h" -o "$1" == "-h" -o "$1" == "-?" -o "$1" == "--?" -o "$1" == "-help" ]; then
    echo "You need to open configure.sh and edit the section where you are shown to do so." 1>&2
    echo "Then run configure.sh with no arguments." 1>&2
    exit 0
fi


# functions
#-----------------------------------------------------------------------------------------
_find_program(){
    for prog in $*
    do
        path=`which $prog 2> /dev/null`
        if [ $? -eq 0 ]; then
            echo $path
            return
        fi
    done
}


# packages path
#-----------------------------------------------------------------------------------------
if [ "$packages_path" == "" ]; then
    echo "You need to set the packages path directory in configure.sh, or set "'$'"REZCONFIG_PACKAGES_PATH" 1>&2
    echo "This is where your rez packages will be centrally deployed to." 1>&2
    exit 1
fi

if [ "`echo $packages_path | grep '^\.'`" != "" ]; then
    echo "Packages path must be an absolute path, not $packages_path" 1>&2
    exit 1
fi


# local packages path
#-----------------------------------------------------------------------------------------
if [ "$local_packages_path" == "" ]; then
    echo "You need to set the local packages path directory in configure.sh, or set "'$'"REZCONFIG_LOCAL_PACKAGES_PATH" 1>&2
    echo "This is where your rez packages will be locally installed to." 1>&2
    exit 1
fi

if [ "`echo $local_packages_path | grep '^\.'`" != "" ]; then
    echo "Local packages path must be an absolute path, not $local_packages_path" 1>&2
    exit 1
fi

if [ "$packages_path" == "$local_packages_path" ]; then
    echo "The local and central package paths must be different." 1>&2
    exit 1
fi

or_set="either specify manually in configure.sh, or set "'$'

nissues=0
echoerr=
echoreset=


# os
#-----------------------------------------------------------------------------------------
if [ "$osname" == "" ]; then
    echo
    echo "Detecting operating system..."
    osname=`uname`
    if [ $? -ne 0 ]; then
        echo "Could not identify operating system - $or_set""REZCONFIG_PLATFORM" 1>&2
        exit 1
    fi
    if [ "$osname" == "Linux" -o "osname" == "Darwin" ]; then
        echoerr=$(tput bold)$(tput setaf 1)
        echoreset=$(tput sgr0)
    fi
    echo "Operating system is: "$osname
fi


# shell
#-----------------------------------------------------------------------------------------
if [ "$rezshell" == "" ]; then
    echo
    echo "detecting shell..."
    rezshell=`basename $SHELL`
    if [ $? -ne 0 ]; then
        echo $echoerr"Could not identify shell - $or_set""REZCONFIG_PLATFORM" 1>&2
        echo "Assuming bash!"$echoreset 1>&2
        rezshell=bash
        nissues=$(( $nissues + 1 ))
    fi
    case "$rezshell" in
        "bash") ;;
    "csh")  ;;
"tcsh") ;;
    *)      echo $echoerr"Unknown shell '"$rezshell"' - $or_set""REZCONFIG_SHELL" 1>&2
        echo "Assuming bash!"$echoreset 1>&2
        rezshell=bash
        nissues=$(( $nissues + 1 ))
        ;;
esac
echo "Shell is: "$rezshell
fi


# distro
#-----------------------------------------------------------------------------------------
# todo generate the distro package
if [ "$distro" == "" ]; then
    echo
    echo 'detecting OS distribution...'
    if [ "$osname" == "Linux" ]; then
        distro=`lsb_release -i | awk '{print $NF}'`
        if [ $? -ne 0 ]; then distro=; fi
    fi
    if [ "$osname" == "Darwin" ]; then
        distro=Apple
    fi
    if [ "$distro" == "" ]; then
        echo $echoerr"Could not identify OS distribution - $or_set""REZCONFIG_DISTRO" 1>&2
        echo "Setting to DISTRO_UNKNOWN-0!"$echoreset 1>&2
        distro=DISTRO_UNKNOWN
        distro_version=0
        nissues=$(( $nissues + 1 ))
    else
        echo "OS distribution is: "$distro
    fi
fi
if [ "$distro_version" == "" ]; then
    echo
    echo 'detecting OS distribution version...'
    if [ "$osname" == "Linux" ]; then
        distro_version=`lsb_release -r | awk '{print $NF}'`
        if [ $? -ne 0 ]; then distro_version=; fi
    fi
    if [ "$osname" == "Darwin" ]; then
        distro_version=`sw_vers -productVersion`
        if [ $? -ne 0 ]; then distro_version=; fi
    fi
    if [ "$distro_version" == "" ]; then
        echo $echoerr"Could not identify OS distribution version - $or_set""REZCONFIG_DISTRO_VERSION" 1>&2
        echo "Setting to 0!"$echoreset 1>&2
        distro_version=0
        nissues=$(( $nissues + 1 ))
    else
        echo "OS distribution version is: "$distro_version
    fi
fi


orset='edit configure.sh, or set $'


# make
#-----------------------------------------------------------------------------------------
which make > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo
    echo "Cannot find make!" 1>&2
    exit 1
fi


# cmake
#-----------------------------------------------------------------------------------------
echo
echo 'detecting cmake...'
if [ "$cmake_binary" == "" ]; then cmake_binary=cmake; fi
which $cmake_binary > /dev/null 2>&1
if [ $? -eq 0 ]; then
    cmake_binary=`which $cmake_binary`
else
    echo "rez.configure: $cmake_binary could not be located - $orset""REZCONFIG_CMAKE_BINARY" 1>&2
    exit 1
fi
echo "found cmake binary: "$cmake_binary

cmakever=`( $cmake_binary --version 2>&1 ) | tr ' ' '\n' | sed -n '/^[0-9]/p' | head -n 1`
versplit=`echo $cmakever | tr '.' ' ' | tr '-' ' '`
cmake_major_ver=`echo $versplit | awk '{print $1}'`
cmake_minor_ver=`echo $versplit | awk '{print $2}'`
if (( (cmake_major_ver * 100) + cmake_minor_ver < 208 )); then
    echo "cmake version "$cmakever" is too old, you need 2.8 or greater." 1>&2
    echo "You need to $orset""REZCONFIG_CMAKE_BINARY" 1>&2
    exit 1
fi


# runtime 3rd-party tools
#-----------------------------------------------------------------------------------------
if [ "$rez_release_editor" == "" ]; then
    rez_release_editor=`_find_program kedit gedit nedit kwrite kate vim vi`
fi
if [ "$rez_dot_image_viewer" == "" ]; then
    rez_dot_image_viewer=`_find_program eog kde-open kview xnview gthumb feh gqview geeqie firefox`
fi


# detect cpp compiler
#-----------------------------------------------------------------------------------------
echo
echo 'detecting cpp compiler...'

# attempt to find compiler via cmake
tmpf=./rez.cppcompiler
echo 'include(CMakeDetermineCXXCompiler)'			> $tmpf
echo 'MESSAGE("REZCXX "${CMAKE_CXX_COMPILER})'		>> $tmpf
echo 'MESSAGE("REZID "${CMAKE_CXX_COMPILER_ID})'	>> $tmpf

cppcompiler=`export CXX=$cpp_compiler_binary ; $cmake_binary -P $tmpf 2>&1 | grep '^REZCXX' | grep -v 'NOTFOUND' | awk '{print $NF}'`
if [ $? -ne 0 ]; then
    cppcompiler=''
fi

cppcompiler_id=`export CXX=$cpp_compiler_binary ; $cmake_binary -P $tmpf 2>&1 | grep '^REZID' | grep -v 'NOTFOUND' | awk '{print $NF}'`
if [ $? -ne 0 ]; then
    cppcompiler_id=''
fi

# couldn't find cpp compiler via cmake, let's just look for the binary directly
if [ "$cppcompiler" == "" ]; then
    echo $echoerr"couldn't find cpp compiler via cmake!"$echoreset 1>&2
    nissues=$(( $nissues + 1 ))
    if [ "$cpp_compiler_binary" == "" ]; then
        cpp_compiler_binary=gcc
    fi
    echo "looking for $cpp_compiler_binary""..." 1>&2
    cppcompiler=`which $cpp_compiler_binary`
    if [ $? -ne 0 ]; then
        echo $echoerr"$cpp_compiler_binary not found."$echoreset 1>&2
        nissues=$(( $nissues + 1 ))
        cppcompiler=''
    else
        echo "found $cpp_compiler_binary at $cppcompiler."
    fi
fi

if [ "$cppcompiler" == "" ]; then
    echo "Couldn't find cpp compiler." 1>&2
    echo "You need to $orset""REZCONFIG_CPP_COMPILER_BINARY" 1>&2
    exit 1
fi

cppcomp_name=`basename $cppcompiler | tr '+' 'p'`

# massage compiler name in some cases
if [ "$cppcompiler_id" == "GNU" ]; then
    if [ "$cppcomp_name" == "cpp" -o "$cppcomp_name" == "gpp" ]; then
        cppcomp_name="gcc"
    fi
    # account for distributions that install various flavours of
    # gcc, each with a different version string appended.
    if [[ "$cppcomp_name" == gcc-* ]]; then
        cppcomp_name="gcc"
    fi
fi
if [ "cppcomp_name" == "gcc" ]; then
    tmp=${cppcompiler/gcc/g++}
    if [ -e $tmp ]; then
        cppcompiler=$tmp
    fi
fi

echo "found cpp compiler: "$cppcompiler", id: "$cppcompiler_id

# detect cpp compiler version
cppcompiler_ver=''
if [ "$cppcompiler_id" == "GNU" ]; then
    ver=`$cppcompiler -dumpversion`
    if [ $? -eq 0 ]; then
        cppcompiler_ver=$ver
    fi
fi
if [ "$cppcompiler_ver" == "" ]; then
    echo $echoerr"Couldn't detect compiler version, assuming 1.0.1..."$echoreset 1>&2
    cppcompiler_ver='1.0.1'
    nissues=$(( $nissues + 1 ))
fi
echo "cpp compiler version: "$cppcompiler_ver


# python
#-----------------------------------------------------------------------------------------
echo
echo 'detecting python...'
if [ "$python_binary" == "" ]; then python_binary=python; fi
which $python_binary > /dev/null 2>&1
if [ $? -eq 0 ]; then
    python_binary=`which $python_binary`
else
    echo "rez.configure: $python_binary could not be located." 1>&2
    echo "You need to $orset""REZCONFIG_PYTHON_BINARY" 1>&2
    exit 1
fi
echo "found python binary: "$python_binary

pyver=`$python_binary -c 'import sys ; v = sys.version_info ; print "%d.%d.%d" % (v[0], v[1], v[2])'`
pynum=`echo $pyver | sed 's/\.[^\.]*$//' | sed 's/\.//'`
if (( pynum < 25 )); then
    echo "python version "$pyver" is too old, you need 2.5 or greater." 1>&2
    echo "You need to $orset""REZCONFIG_PYTHON_BINARY" 1>&2
    exit 1
fi
echo "python version: "$pyver

#
# On the Mac, /usr/bin/python is a special file, and when we create
# a symlink to it for rezpy, executing rezpy fails with this error:
# rezpy: realpath couldn't resolve "/usr/bin/rezpy"
# so if we're using the system python, we go set python_binary to the real python
# that has a version number (/usr/bin/python2.5, /usr/bin/python2.6 or /usr/bin/python2.7)
# as of mountain lion.
#
if [ "$osname" == "Darwin" -a "$python_binary" == "/usr/bin/python" ]; then
    python_binary=/usr/bin/python`defaults read com.apple.versioner.python Version`
fi

# pyyaml
#-----------------------------------------------------------------------------------------
echo
echo 'detecting pyyaml...'
if [ "$pyyaml_path" == "" ]; then
    $python_binary -c "import yaml" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        pyyaml_path=`$python_binary -c \
            "import os.path ; \
            import yaml ; \
            s = yaml.__file__.replace('/__init__.pyc','') ; \
            s = yaml.__file__.replace('/__init__.pyo','') ; \
            s = s.replace('/__init__.py','') ; \
            print os.path.dirname(s)"`
        if [ $? -ne 0 ]; then
            pyyaml_path=""
        fi
    fi
fi
if [ "$pyyaml_path" == "" ]; then
    echo "couldn't find yaml python module - $orset""REZCONFIG_PYYAML_PATH" 1>&2
    exit 1
else
    bash -c "export PYTHONPATH=$pyyaml_path ; $python_binary -c 'import yaml' > /dev/null 2>&1"
    if [ $? -ne 0 ]; then
        echo "yaml python module not found at "$pyyaml_path 1>&2
        exit 1
    fi
fi
echo "found pyyaml at "$pyyaml_path


# pydot
#-----------------------------------------------------------------------------------------
echo
echo 'detecting pydot...'
if [ "$pydot_path" == "" ]; then
    $python_binary -c "import pydot" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        pydot_path=`$python_binary -c \
            "import os.path ; \
            import pydot ; \
            s = pydot.__file__.replace('/__init__.pyc','') ; \
            s = pydot.__file__.replace('/__init__.pyo','') ; \
            s = s.replace('/__init__.py','') ; \
            print os.path.dirname(s)"`
        if [ $? -ne 0 ]; then
            pydot_path=""
        fi
    fi
fi
if [ "$pydot_path" == "" ]; then
    echo "couldn't find pydot python module - $orset""REZCONFIG_PYDOT_PATH" 1>&2
    exit 1
else
    bash -c "export PYTHONPATH=$pydot_path ; $python_binary -c 'import pydot' > /dev/null 2>&1"
    if [ $? -ne 0 ]; then
        echo "pydot python module not found at "$pydot_path 1>&2
        exit 1
    fi
fi
echo "found pydot at "$pydot_path


# pyparsing
#-----------------------------------------------------------------------------------------
echo
echo 'detecting pyparsing...'
if [ "$pyparsing_path" == "" ]; then
    $python_binary -c "import pyparsing" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        pyparsing_path=`$python_binary -c \
            "import os.path ; \
            import pyparsing ; \
            s = pyparsing.__file__.replace('/__init__.pyc','') ; \
            s = pyparsing.__file__.replace('/__init__.pyo','') ; \
            s = s.replace('/__init__.py','') ; \
            print os.path.dirname(s)"`
        if [ $? -ne 0 ]; then
            pyparsing_path=""
        fi
    fi
fi
if [ "$pyparsing_path" == "" ]; then
    echo "couldn't find pyparsing python module - $orset""REZCONFIG_PYPARSING_PATH" 1>&2
    exit 1
else
    bash -c "export PYTHONPATH=$pyparsing_path ; $python_binary -c 'import pyparsing' > /dev/null 2>&1"
    if [ $? -ne 0 ]; then
        echo "pyparsing python module not found at "$pyparsing_path 1>&2
        exit 1
    fi
fi
echo "found pyparsing at "$pyparsing_path


if [ "$_REZ_ISDEMO" != "1" ]; then
    # pymemcached
    #-----------------------------------------------------------------------------------------
    echo
    echo 'detecting pymemcached...'
    if [ "$pymemcached_path" == "" ]; then
        $python_binary -c "import memcache" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            pymemcached_path=`$python_binary -c \
                "import os.path ; \
                import memcache ; \
                s = memcache.__file__.replace('/__init__.pyc','') ; \
                s = memcache.__file__.replace('/__init__.pyo','') ; \
                s = s.replace('/__init__.py','') ; \
                print os.path.dirname(s)"`
            if [ $? -ne 0 ]; then
                pymemcached_path=""
            fi
        fi
    fi
    if [ "$pymemcached_path" == "" ]; then
        echo $echoerr"couldn't find memcache python module - $orset""REZCONFIG_PYMEMCACHED_PATH"$echoreset 1>&2
    else
        bash -c "export PYTHONPATH=$pymemcached_path ; $python_binary -c 'import memcache' > /dev/null 2>&1"
        if [ $? -ne 0 ]; then
            echo $echoerr"memcache python module not found at "${pymemcached_path}$echoreset 1>&2
            pymemcached_path=""
        fi
    fi
    if [ "$pymemcached_path" == "" ]; then
        echo "Installation can continue, but caching will not be available." 1>&2
        echo "To enable later, just add the python-memcached python path where it is missing in (rez-install-path)/bin/_set-rez-env" 1>&2
        nissues=$(( $nissues + 1 ))
    else
        echo "found python-memcached at "$pymemcached_path
    fi

    # pysvn
    #-----------------------------------------------------------------------------------------
    echo
    echo 'detecting pysvn...'
    if [ "$pysvn_path" == "" ]; then
        $python_binary -c "import pysvn" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            pysvn_path=`$python_binary -c \
                "import os.path ; \
                import pysvn ; \
                s = pysvn.__file__.replace('/__init__.pyc','') ; \
                s = pysvn.__file__.replace('/__init__.pyo','') ; \
                s = s.replace('/__init__.py','') ; \
                print os.path.dirname(s)"`
            if [ $? -ne 0 ]; then
                pysvn_path=""
            fi
        fi
    fi
    if [ "$pysvn_path" == "" ]; then
        echo $echoerr"couldn't find pysvn python module - $orset""REZCONFIG_PYSVN_PATH"$echoreset 1>&2
    else
        bash -c "export PYTHONPATH=$pysvn_path ; $python_binary -c 'import pysvn' > /dev/null 2>&1"
        if [ $? -ne 0 ]; then
            echo $echoerr"pysvn python module not found at "${pysvn_path}$echoreset 1>&2
            pysvn_path=""
        fi
    fi
    if [ "$pysvn_path" == "" ]; then
        echo "Installation can continue, but rez-release for svn will not be available." 1>&2
        echo "To enable later, just add the svn python path where it is missing in (rez-install-path)/bin/_set-rez-env" 1>&2
        nissues=$(( $nissues + 1 ))
    else
        echo "found pysvn at "$pysvn_path
    fi

    # gitpython
    #-----------------------------------------------------------------------------------------
    echo
    echo 'detecting gitpython...'
    if [ "$gitpython_path" == "" ]; then
        $python_binary -c "import git" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            gitpython_path=`$python_binary -c \
                "import os.path ; \
                import git ; \
                s = git.__file__.replace('/__init__.pyc','') ; \
                s = git.__file__.replace('/__init__.pyo','') ; \
                s = s.replace('/__init__.py','') ; \
                print os.path.dirname(s)"`
            if [ $? -ne 0 ]; then
                gitpython_path=""
            fi
        fi
    fi
    if [ "$gitpython_path" == "" ]; then
        echo $echoerr"couldn't find gitpython python module - $orset""REZCONFIG_GITPYTHON_PATH"$echoreset 1>&2
    else
        bash -c "export PYTHONPATH=$gitpython_path ; $python_binary -c 'import git' > /dev/null 2>&1"
        if [ $? -ne 0 ]; then
            echo $echoerr"gitpython python module not found at "${gitpython_path}$echoreset 1>&2
            gitpython_path=""
        fi
    fi
    if [ "$gitpython_path" == "" ]; then
        echo "Installation can continue, but rez-release for git will not be available." 1>&2
        echo "To enable later, just add the git python path where it is missing in (rez-install-path)/bin/_set-rez-env" 1>&2
        nissues=$(( $nissues + 1 ))
    else
        echo "found gitpython at "$gitpython_path
    fi
fi


# write configuration info
#-----------------------------------------------------------------------------------------
echo "# generated by configure.sh" 						            > ./rez.configured
echo "export _REZ_PACKAGES_PATH='"$packages_path"'"				    >> ./rez.configured
echo "export _REZ_LOCAL_PACKAGES_PATH='"$local_packages_path"'"	    >> ./rez.configured
echo "export _REZ_SHELL='"$rezshell"'"                              >> ./rez.configured
echo "export _REZ_PLATFORM='"$osname"'"						        >> ./rez.configured
echo "export _REZ_DISTRO='"$distro"'"						        >> ./rez.configured
echo "export _REZ_DISTRO_VER='"$distro_version"'"					>> ./rez.configured
echo "export _REZ_CMAKE_BINARY='"$cmake_binary"'"				    >> ./rez.configured
echo "export _REZ_CPP_COMPILER='"$cppcompiler"'"				    >> ./rez.configured
echo "export _REZ_CPP_COMPILER_NAME='"$cppcomp_name"'"				>> ./rez.configured
echo "export _REZ_CPP_COMPILER_ID='"$cppcompiler_id"'"				>> ./rez.configured
echo "export _REZ_CPP_COMPILER_VER='"$cppcompiler_ver"'"			>> ./rez.configured
echo "export _REZ_PYTHON_BINARY='"$python_binary"'"				    >> ./rez.configured
echo "export _REZ_PYTHON_VER='"$pyver"'"					        >> ./rez.configured
echo "export _REZ_PYYAML_PATH='"$pyyaml_path"'" 				    >> ./rez.configured
echo "export _REZ_PYDOT_PATH='"$pydot_path"'"	 				    >> ./rez.configured
echo "export _REZ_PYPARSING_PATH='"$pyparsing_path"'"				>> ./rez.configured
echo "export _REZ_PYMEMCACHED_PATH='"$pymemcached_path"'"	 		>> ./rez.configured
echo "export _REZ_PYSVN_PATH='"$pysvn_path"'"	 				    >> ./rez.configured
echo "export _REZ_GITPYTHON_PATH='"$gitpython_path"'"	 			>> ./rez.configured
echo "export _REZ_RELEASE_EDITOR='"$rez_release_editor"'"	 	    >> ./rez.configured
echo "export _REZ_DOT_IMAGE_VIEWER='"$rez_dot_image_viewer"'"	 	>> ./rez.configured

echo
if [ $nissues -ne 0 ]; then
    echo $echoerr"There were $nissues issues, please review above. Note that installation has still succeeded."$echoreset
fi
echo "rez.configured written."
echo "Now run ./install.sh"
echo





#    Copyright 2012 BlackGinger Pty Ltd (Cape Town, South Africa)
#
#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
