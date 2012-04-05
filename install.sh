#!/bin/bash
#
# Installation script for rez.
#
# Note that this has only been tested on linux (Centos5).
#
# usage: install.sh <rez_install_path>
# example: install.sh /foo/bah/rez
# Actual install path will be prefixed with the rez version
#
#
#

# setup
#-----------------------------------------------------------------------------------------

# cd into same dir as this script
absfpath=`[[ $0 == /* ]] && echo "$0" || echo "${PWD}/${0#./}"`
cwd=`dirname $absfpath`
cd $cwd

. ./version.sh

if [ ! -e ./rez.configured ]; then
	echo "need to run configure.sh first." 1>&2
	exit 1
fi
source ./rez.configured

if [ $# -ne 1 ]; then
	echo "usage: install.sh <rez_install_path>" 1>&2
	exit 1
fi

install_dir=$1"/"$rez_version
if [ -e $install_dir ]; then
	rm -rf $install_dir/*
else
	mkdir -p $install_dir
	if [ ! -e $install_dir ]; then
		echo "couldn't create dir $install_dir." 1>&2
		exit 1
	fi
fi


# create bootstrap packages
#-----------------------------------------------------------------------------------------

mkdir -p $_REZ_PACKAGES_PATH
if [ ! -e $_REZ_PACKAGES_PATH ]; then
	echo "couldn't create directory $_REZ_PACKAGES_PATH"
	exit 1
fi


# operating system
#------------------
osname=$_REZ_PLATFORM
os_dir=$_REZ_PACKAGES_PATH/$osname
rm -rf $os_dir
mkdir -p $os_dir/cmake
os_yaml=$os_dir/package.yaml

echo "config_version : 0" 			> $os_yaml
echo "name: $osname" 				>> $os_yaml
echo "commands:" 					>> $os_yaml
echo '- export CMAKE_MODULE_PATH=$CMAKE_MODULE_PATH:!ROOT!/cmake'	>> $os_yaml

os_cmake=$os_dir/cmake/$osname.cmake
echo '' > $os_cmake
if [ "$osname" == "Linux" ]; then
	echo "set(lin64_LIBRARIES dl z)"					>> $os_cmake
	echo "set(lin64_DEFINITIONS -fPIC -m64 -DLINUX)"	>> $os_cmake
fi


# cmake
#------------------
cmake_ver=`( $_REZ_CMAKE_BINARY --version 2>&1 ) | awk '{print $NF}'`
cmake_dir=$_REZ_PACKAGES_PATH/cmake/$cmake_ver
rm -rf $cmake_dir
mkdir -p $cmake_dir/$osname/bin
ln -s $_REZ_CMAKE_BINARY $cmake_dir/$osname/bin/cmake
cmake_yaml=$cmake_dir/package.yaml

echo "config_version : 0" 				> $cmake_yaml
echo "name: cmake" 						>> $cmake_yaml
echo "version: "$cmake_ver 				>> $cmake_yaml
echo "variants:"						>> $cmake_yaml
echo "- [ $osname ]"					>> $cmake_yaml
echo "commands:" 						>> $cmake_yaml
echo '- export PATH=$PATH:!ROOT!/bin'	>> $cmake_yaml

# cpp compiler
#------------------
cppcomp_dir=$_REZ_PACKAGES_PATH/$_REZ_CPP_COMPILER_NAME/$_REZ_CPP_COMPILER_VER
rm -rf $cppcomp_dir
mkdir -p $cppcomp_dir/$osname/cmake

c_binary=$_REZ_CPP_COMPILER 
cpp_binary=$_REZ_CPP_COMPILER
if [ "$_REZ_CPP_COMPILER_NAME" == "gcc" ]; then
	cpp_binary=${cpp_binary/gcc/g++}
fi

cppcomp_yaml=$cppcomp_dir/package.yaml
echo "config_version : 0" 				> $cppcomp_yaml
echo "name: $_REZ_CPP_COMPILER_NAME" 	>> $cppcomp_yaml
echo "version: "$_REZ_CPP_COMPILER_VER 	>> $cppcomp_yaml
echo "variants:"						>> $cppcomp_yaml
echo "- [ $osname ]"					>> $cppcomp_yaml
echo "commands:" 						>> $cppcomp_yaml
echo "- export CXX=$cpp_binary"			>> $cppcomp_yaml

# python
#------------------
py_ver=$_REZ_PYTHON_VER
py_dir=$_REZ_PACKAGES_PATH/python/$py_ver
rm -rf $py_dir
mkdir -p $py_dir/$osname/bin
# shebanged python scripts in rez packages should shebang to '/usr/bin/env rezpy', so
# that they are using the correctly configured version of python when they execute.
ln -s $_REZ_PYTHON_BINARY $py_dir/$osname/bin/rezpy
py_yaml=$py_dir/package.yaml

echo "config_version : 0" 				> $py_yaml
echo "name: python" 					>> $py_yaml
echo "version: "$py_ver 				>> $py_yaml
echo "variants:"					>> $py_yaml
echo "- [ $osname ]"					>> $py_yaml
echo "commands:" 					>> $py_yaml
echo '- export PATH=$PATH:!ROOT!/bin'			>> $py_yaml


# example package
#------------------
pkg_dir=$_REZ_PACKAGES_PATH/hello_world
rm -rf $pkg_dir
mkdir -p $pkg_dir/$osname/bin

pkg_sh=$pkg_dir/$osname/bin/hello_world
echo "#!/bin/bash"					> $pkg_sh
echo "rez-context-info"					>> $pkg_sh
echo "echo 'Hello world!'"				>> $pkg_sh
chmod 777 $pkg_sh

pkg_yaml=$pkg_dir/package.yaml
echo "config_version : 0" 				> $pkg_yaml
echo "name: hello_world" 				>> $pkg_yaml
echo "variants:"						>> $pkg_yaml
echo "- [ $osname ]"					>> $pkg_yaml
echo "commands:" 						>> $pkg_yaml
echo '- export PATH=$PATH:!ROOT!/bin'	>> $pkg_yaml

# install init.sh
#-----------------------------------------------------------------------------------------
cat ./init.sh \
	| sed -e 's|!REZ_VERSION!|'$rez_version'|g' \
	| sed -e 's|!REZ_PLATFORM!|'$osname'|g' \
	| sed -e 's|!REZ_BASE_PATH!|'$1'|g' \
	| sed -e 's|!REZ_LOCAL_PKGS_PATH!|'$_REZ_LOCAL_PACKAGES_PATH'|g' \
	| sed -e 's|!REZ_PACKAGES_PATH!|'$_REZ_PACKAGES_PATH'|g' \
	| sed -e 's|!REZ_RELEASE_EDITOR!|'$_REZ_RELEASE_EDITOR'|g' \
	| sed -e 's|!REZ_DOT_IMAGE_VIEWER!|'$_REZ_DOT_IMAGE_VIEWER'|g' \
	> $install_dir/init.sh

# install init.csh
#-----------------------------------------------------------------------------------------
cat ./init.csh \
	| sed -e 's|!REZ_VERSION!|'$rez_version'|g' \
	| sed -e 's|!REZ_PLATFORM!|'$osname'|g' \
	| sed -e 's|!REZ_BASE_PATH!|'$1'|g' \
	| sed -e 's|!REZ_LOCAL_PKGS_PATH!|'$_REZ_LOCAL_PACKAGES_PATH'|g' \
	| sed -e 's|!REZ_PACKAGES_PATH!|'$_REZ_PACKAGES_PATH'|g' \
	| sed -e 's|!REZ_RELEASE_EDITOR!|'$_REZ_RELEASE_EDITOR'|g' \
	| sed -e 's|!REZ_DOT_IMAGE_VIEWER!|'$_REZ_DOT_IMAGE_VIEWER'|g' \
	> $install_dir/init.csh

# install bin/ files
#-----------------------------------------------------------------------------------------
mkdir -p $install_dir/bin
cat ./bin/_set-rez-env \
	| sed -e 's|!REZ_PYYAML_PATH!|'$_REZ_PYYAML_PATH'|g' \
	| sed -e 's|!REZ_PYDOT_PATH!|'$_REZ_PYDOT_PATH'|g' \
	| sed -e 's|!REZ_PYPARSING_PATH!|'$_REZ_PYPARSING_PATH'|g' \
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
		chmod 777 $install_dir/bin/$f
	fi
done

# install remaining files
#-----------------------------------------------------------------------------------------
cp -rf ./cmake $install_dir
cp -rf ./template $install_dir

# finish up
#-----------------------------------------------------------------------------------------

echo
echo "rez install successful!"
echo "Initial boostrap packages have been created in: "$_REZ_PACKAGES_PATH
echo
echo "to test in bash, try running this:"
echo
echo "unset REZ_PACKAGES_PATH ; source $install_dir/init.sh ; rez run hello_world"
echo
echo "to test in csh, try running this:"
echo
echo "unsetenv REZ_PACKAGES_PATH; source $install_dir/init.csh; rez run hello_world"
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
