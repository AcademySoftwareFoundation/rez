#
# System initialization script for rez. Source this file in order to use rez. You probably
# want to do that in ~/.cshrc or equivalent startup script.
#

# rez version
setenv REZ_VERSION !REZ_VERSION!

# rez OS
setenv REZ_PLATFORM !REZ_PLATFORM!

# where rez is installed
setenv REZ_PATH !REZ_BASE_PATH!/!REZ_VERSION!
if (! -d $REZ_PATH ) then
    echo "ERROR! Rez could not be found at $REZ_PATH" 1>&2
else

    # where rez searches for packages
    if (! $?REZ_PACKAGES_PATH ) then
        setenv REZ_PACKAGES_PATH !REZ_LOCAL_PKGS_PATH!:!REZ_PACKAGES_PATH!
    endif


    # where rez will publish packages to (ie those released with rez-release)
    if (! $?REZ_RELEASE_PACKAGES_PATH ) then
        setenv REZ_RELEASE_PACKAGES_PATH !REZ_PACKAGES_PATH!
    endif


    # where rez will publish local packages to (ie those installed with rez-build -- -- install)
    if (! $?REZ_LOCAL_PACKAGES_PATH ) then
        setenv REZ_LOCAL_PACKAGES_PATH !REZ_LOCAL_PKGS_PATH!
    endif


    # where rez-egg-install will install python egg packages to
    if (! $?REZ_EGG_PACKAGES_PATH ) then
        setenv REZ_EGG_PACKAGES_PATH !REZ_PACKAGES_PATH!
    endif


    # expose rez binaries, replacing existing rez paths if they have been set already
    set clean_path = `echo "$PATH" | /usr/bin/tr ':' '\n' | grep -v '^$' | grep -v '!REZ_BASE_PATH!' | /usr/bin/tr '\n' ':'`
    setenv PATH ${clean_path}:${REZ_PATH}/bin

    # TODO: Allow for nice tab-completion for csh
    #source $REZ_PATH/bin/_complete.csh
endif





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
