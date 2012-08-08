#!/bin/bash

export REZ_WRAPPER_CONTEXT=`dirname $0`/#CONTEXT#
source $REZ_WRAPPER_CONTEXT
source $REZ_PATH/init.sh

if [ "${!#}" == "---i" ]; then
	export REZ_ENV_PROMPT="${REZ_ENV_PROMPT}#CONTEXTNAME#>"
	/bin/bash --rcfile $REZ_PATH/bin/rez-env-bashrc
	exit $?
elif [ "${!#}" == "---s" ]; then
	if [ -f ~/.bashrc ]; then
		source ~/.bashrc &> /dev/null
	fi
	/bin/bash -s
	exit $?
else
	patch=`echo $* | grep '\-\-\-p'`
	if [ "$patch" == "" ]; then
		if [ -f ~/.bashrc ]; then
			source ~/.bashrc &> /dev/null
		fi
		#ALIAS# $*
		exit $?
	else
		args=`echo $* | sed 's/---p.*//g'`
		pkgs=`echo $* | sed 's/.*---p//g'`
		( echo rez-context-info ; echo '#ALIAS#' $args ) | rez-env -s -a $pkgs
		exit $?
	fi
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
