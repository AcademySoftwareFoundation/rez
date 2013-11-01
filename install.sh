#!/bin/bash
#
# Installation script for rez.
#
# usage: install.sh [options] [install_path]
# example: install.sh /centralsvr/software/ext/rez
# Actual install path will be appended with the rez version.
#
# If you're developing rez and want to install a new version, do the following:
# 1) Update the version number in version.sh;
# 2) Run ./install.sh, with no arguments.
# After the first install, a 'rez.installed' file is created, which stores the install directory so
# you don't have to keep specifying it. Further installs will also skip one-off actions, such as
# creating the bootstrap packages. To force a new full install, delete rez.installed, then install.
#

# cmdlin
#-----------------------------------------------------------------------------------------
function usage {
    echo "usage: install [options] [install_path]"
    echo "install_path must be specified the first time, after this a ./rez.installed file is"
    echo "created, which remembers where to install. To change install path, remove this file."
    echo "options:"
    echo "  -n: disable creation of bootstrap packages (default if rez.installed is present)"
}

function make_pkg_dir {
    rm -rf $1
    mkdir -p $1/.metadata
    date +%s > $1/.metadata/release_time.txt
}

# cd into same dir as this script
absfpath=`[[ $0 == /* ]] && echo "$0" || echo "${PWD}/${0#./}"`
cwd=`dirname $absfpath`
cd $cwd

. ./version.sh

reinstall=0
create_bootstrap_pkgs=1

if [ -e ./rez.installed -a "$_REZ_ISDEMO" != "1" ]; then
    reinstall=1
    create_bootstrap_pkgs=0
    base_install_dir=`cat ./rez.installed`
fi

if [ ! -e ./rez.configured ]; then
    echo "need to run configure.sh first." 1>&2
    exit 1
fi
. ./rez.configured

# parse options
while getopts "n" opt; do
    case $opt in
    n)  create_bootstrap_pkgs=0
        ;;
    \?)
        usage
        exit 1
    esac
done

shift $((OPTIND-1))
if [ $reinstall -eq 0 -a $# -eq 0 ]; then
    usage
    exit 0
fi


# setup
#-----------------------------------------------------------------------------------------
if [ $reinstall -eq 1 ]; then
    echo "Detected previous install base path: "$base_install_dir
    if [ $# -gt 0 ]; then
        echo "Please either don't specify an install path, or delete rez.installed first." 1>&2
        echo "Rez is not sure what you want to do. See notes at the top of install.sh for more details." 1>&2
        exit 1
    fi
else
    if [ $# -ne 1 ]; then
        echo "usage: install.sh <rez_install_path>" 1>&2
        exit 1
    fi

    base_install_dir=`echo $1 | sed 's|/$||'`
    tmp=`echo $_REZ_PACKAGES_PATH | grep "^$base_install_dir"`
    if [ "$tmp" != "" ]; then
        echo "the packages path must not be a subdirectory of the install path, please change either and try again." 1>&2
        exit 1
    fi
fi

install_dir=$base_install_dir"/"$rez_version
if [ -e $install_dir ]; then
    rm -rf $install_dir/*
else
    mkdir -p $install_dir
    chmod 755 $base_install_dir
    chmod 755 $install_dir
    if [ ! -e $install_dir ]; then
        echo "couldn't create dir $install_dir." 1>&2
        exit 1
    fi
fi


if [ $create_bootstrap_pkgs -eq 1 ]; then
    # create bootstrap packages
    #-----------------------------------------------------------------------------------------
    # todo move some of these into dedicated rez-find code, which will eventually deprecate the
    # find code in configure.sh

    mkdir -p $_REZ_PACKAGES_PATH
    if [ ! -e $_REZ_PACKAGES_PATH ]; then
        echo "couldn't create directory $_REZ_PACKAGES_PATH"
        exit 1
    fi


    # operating system
    #------------------
    osname=$_REZ_PLATFORM
    os_dir=$_REZ_PACKAGES_PATH/$osname
    make_pkg_dir $os_dir
    mkdir -p $os_dir/cmake
    os_yaml=$os_dir/package.yaml

    os_bits='64'
    test_bits=`getconf LONG_BIT`
    if [ $? -eq 0 ]; then
        os_bits=$test_bits
    fi

    echo "config_version : 0" 			> $os_yaml
    echo "name: $osname" 			>> $os_yaml
    echo "commands:" 				>> $os_yaml
    echo '- export CMAKE_MODULE_PATH=$CMAKE_MODULE_PATH:!ROOT!/cmake'	>> $os_yaml

    os_cmake=$os_dir/cmake/$osname.cmake
    echo '' > $os_cmake
    if [ "$osname" == "Linux" ]; then
        echo "#set(Linux_LIBRARIES dl z)"		        >> $os_cmake
        echo "set(Linux_DEFINITIONS -fPIC -m$os_bits -DLINUX)"  >> $os_cmake
    fi


    # cmake
    #------------------
    cmake_ver=`( $_REZ_CMAKE_BINARY --version 2>&1 ) | awk '{print $NF}'`
    cmake_dir=$_REZ_PACKAGES_PATH/cmake/$cmake_ver
    make_pkg_dir $cmake_dir
    mkdir -p $cmake_dir/$osname/bin
    ln -s $_REZ_CMAKE_BINARY $cmake_dir/$osname/bin/cmake
    cmake_yaml=$cmake_dir/package.yaml

    echo "config_version : 0" 			> $cmake_yaml
    echo "name: cmake" 				>> $cmake_yaml
    echo "version: "$cmake_ver 			>> $cmake_yaml
    echo "variants:"				>> $cmake_yaml
    echo "- [ $osname ]"			>> $cmake_yaml
    echo "commands:" 				>> $cmake_yaml
    echo '- export PATH=$PATH:!ROOT!/bin'	>> $cmake_yaml


    # cpp compiler
    #------------------
    cppcomp_dir=$_REZ_PACKAGES_PATH/$_REZ_CPP_COMPILER_NAME/$_REZ_CPP_COMPILER_VER
    make_pkg_dir $cppcomp_dir
    mkdir -p $cppcomp_dir/$osname/cmake

    c_binary=$_REZ_CPP_COMPILER
    cpp_binary=$_REZ_CPP_COMPILER

    cppcomp_yaml=$cppcomp_dir/package.yaml
    echo "config_version : 0" 			> $cppcomp_yaml
    echo "name: $_REZ_CPP_COMPILER_NAME" 	>> $cppcomp_yaml
    echo "version: "$_REZ_CPP_COMPILER_VER 	>> $cppcomp_yaml
    echo "variants:"				>> $cppcomp_yaml
    echo "- [ $osname ]"			>> $cppcomp_yaml
    echo "commands:" 				>> $cppcomp_yaml
    echo "- export CXX=$cpp_binary"		>> $cppcomp_yaml


    # python
    #------------------
    py_ver=$_REZ_PYTHON_VER
    py_dir=$_REZ_PACKAGES_PATH/python/$py_ver
    make_pkg_dir $py_dir
    mkdir -p $py_dir/$osname/bin
    ln -s $_REZ_PYTHON_BINARY $py_dir/$osname/bin/rezpy
    ln -s $_REZ_PYTHON_BINARY $py_dir/$osname/bin/python
    py_yaml=$py_dir/package.yaml

    echo "config_version : 0" 		  > $py_yaml
    echo "name: python" 		  >> $py_yaml
    echo "version: "$py_ver 		  >> $py_yaml
    echo "variants:"			  >> $py_yaml
    echo "- [ $osname ]"		  >> $py_yaml
    echo "commands:" 			  >> $py_yaml
    echo '- export PATH=$PATH:!ROOT!/bin' >> $py_yaml


    # example package
    #------------------
    pkg_dir=$_REZ_PACKAGES_PATH/hello_world
    make_pkg_dir $pkg_dir
    mkdir -p $pkg_dir/bin
    pkg_sh=$pkg_dir/bin/hello_world
    echo "#!/bin/bash"			        > $pkg_sh
    echo "echo 'Hello world!'"			>> $pkg_sh
    chmod 755 $pkg_sh

    pkg_yaml=$pkg_dir/package.yaml
    echo "config_version : 0" 			> $pkg_yaml
    echo "name: hello_world" 			>> $pkg_yaml
    echo "tools:"                               >> $pkg_yaml
    echo "- hello_world"                        >> $pkg_yaml
    echo "commands:" 				>> $pkg_yaml
    echo '- export PATH=$PATH:!ROOT!/bin'	>> $pkg_yaml
fi


# install init.sh
#-----------------------------------------------------------------------------------------
cat ./init.sh \
    | sed -e 's|!REZ_PATH!|'$install_dir'|g' \
    | sed -e 's|!REZ_VERSION!|'$rez_version'|g' \
    | sed -e 's|!REZ_PLATFORM!|'$osname'|g' \
    | sed -e 's|!REZ_BASE_PATH!|'$base_install_dir'|g' \
    | sed -e 's|!REZ_LOCAL_PKGS_PATH!|'$_REZ_LOCAL_PACKAGES_PATH'|g' \
    | sed -e 's|!REZ_PACKAGES_PATH!|'$_REZ_PACKAGES_PATH'|g' \
    | sed -e 's|!REZ_RELEASE_EDITOR!|'$_REZ_RELEASE_EDITOR'|g' \
    | sed -e 's|!REZ_DOT_IMAGE_VIEWER!|'$_REZ_DOT_IMAGE_VIEWER'|g' \
    > $install_dir/init.sh
chmod 644 $install_dir/init.sh

# install init.csh
#-----------------------------------------------------------------------------------------
cat ./init.csh \
    | sed -e 's|!REZ_PATH!|'$install_dir'|g' \
    | sed -e 's|!REZ_VERSION!|'$rez_version'|g' \
    | sed -e 's|!REZ_PLATFORM!|'$osname'|g' \
    | sed -e 's|!REZ_BASE_PATH!|'$base_install_dir'|g' \
    | sed -e 's|!REZ_LOCAL_PKGS_PATH!|'$_REZ_LOCAL_PACKAGES_PATH'|g' \
    | sed -e 's|!REZ_PACKAGES_PATH!|'$_REZ_PACKAGES_PATH'|g' \
    | sed -e 's|!REZ_RELEASE_EDITOR!|'$_REZ_RELEASE_EDITOR'|g' \
    | sed -e 's|!REZ_DOT_IMAGE_VIEWER!|'$_REZ_DOT_IMAGE_VIEWER'|g' \
    > $install_dir/init.csh
chmod 644 $install_dir/init.csh

# install bin/ files
#-----------------------------------------------------------------------------------------
mkdir -p $install_dir/bin
chmod 755 $install_dir/bin
cat ./bin/_set-rez-env \
    | sed -e 's|!REZ_PATH!|'$install_dir'|g' \
    | sed -e 's|!REZ_PYYAML_PATH!|'$_REZ_PYYAML_PATH'|g' \
    | sed -e 's|!REZ_PYDOT_PATH!|'$_REZ_PYDOT_PATH'|g' \
    | sed -e 's|!REZ_PYPARSING_PATH!|'$_REZ_PYPARSING_PATH'|g' \
    | sed -e 's|!REZ_PYMEMCACHED_PATH!|'$_REZ_PYMEMCACHED_PATH'|g' \
    | sed -e 's|!REZ_PYSVN_PATH!|'$_REZ_PYSVN_PATH'|g' \
    | sed -e 's|!REZ_GITPYTHON_PATH!|'$_REZ_GITPYTHON_PATH'|g' \
    > $install_dir/bin/_set-rez-env

binfiles=`ls ./bin | grep -v '_set-rez-env'`
for f in $binfiles
do
    cat ./bin/$f \
        | sed -e 's|!REZ_PYTHON_BINARY!|'$_REZ_PYTHON_BINARY'|g' \
        > $install_dir/bin/$f

    shebang=`cat ./bin/$f | grep -n '^#!' | tr ':' ' ' | awk '{print $1}'`
    if [ "$shebang" == "1" ]; then
        chmod 755 $install_dir/bin/$f
    fi
done

# install remaining files
#-----------------------------------------------------------------------------------------
cp -rf ./python $install_dir
chmod 755 `find $install_dir/python -type d`
chmod 644 `find $install_dir/python -type f`
cp -rf ./cmake $install_dir
chmod 755 `find $install_dir/cmake -type d`
chmod 644 `find $install_dir/cmake -type f`
cp -rf ./template $install_dir
chmod 755 `find $install_dir/template -type d`
chmod 644 `find $install_dir/template -type f`

# finish up
#-----------------------------------------------------------------------------------------

echo
echo "rez $rez_version installed successfully."

if [ $reinstall -eq 0 -a "$_REZ_ISDEMO" != "1" ]; then
    echo $base_install_dir > ./rez.installed

    echo "Initial boostrap packages have been created in: "$_REZ_PACKAGES_PATH
    echo
    echo "to test, try running this:"
    ext=csh
    if [ "$_REZ_SHELL" == "bash" ]; then ext=sh; fi
    echo "unset REZ_PACKAGES_PATH ; source $install_dir/init.$ext ; rez run hello_world"
fi

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
