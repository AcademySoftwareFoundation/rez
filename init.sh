#
# System initialization script for rez. Source this file in order to use rez. You probably
# want to do that in ~/.bashrc or equivalent startup script.
#

# rez version
export REZ_VERSION=!REZ_VERSION!

# rez OS
export REZ_PLATFORM=!REZ_PLATFORM!

# where rez is installed
export REZ_PATH=!REZ_BASE_PATH!/!REZ_VERSION!
if [ ! -d $REZ_PATH ]; then
	echo "ERROR! Rez could not be found at $REZ_PATH" 1>&2
else

	# where rez searches for packages
	if [ "$REZ_PACKAGES_PATH" == "" ]; then
		export REZ_PACKAGES_PATH=!REZ_LOCAL_PKGS_PATH!:!REZ_PACKAGES_PATH!
	fi


	# where rez will publish packages to (ie those released with rez-release)
	if [ "$REZ_RELEASE_PACKAGES_PATH" == "" ]; then
		export REZ_RELEASE_PACKAGES_PATH=!REZ_PACKAGES_PATH!
	fi


	# where rez will publish local packages to (ie those installed with rez-build -- -- install)
	if [ "$REZ_LOCAL_PACKAGES_PATH" == "" ]; then
		export REZ_LOCAL_PACKAGES_PATH=!REZ_LOCAL_PKGS_PATH!
	fi


	# where rez-egg-install will install python egg packages to
	if [ "$REZ_EGG_PACKAGES_PATH" == "" ]; then
		export REZ_EGG_PACKAGES_PATH=!REZ_PACKAGES_PATH!
	fi

	# expose rez binaries, replacing existing rez paths if they have been set already
	PATH=`echo $PATH | /usr/bin/tr ':' '\n' | grep -v '^$' | grep -v '!REZ_BASE_PATH!' | /usr/bin/tr '\n' ':'`
	export PATH=$PATH:$REZ_PATH/bin

	source $REZ_PATH/bin/_complete
fi






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
