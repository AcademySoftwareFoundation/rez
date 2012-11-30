#!/bin/bash

export REZ_WRAPPER_CONTEXT=`dirname $0`/#CONTEXT#
export REZ_WRAPPER_NAME='#CONTEXTNAME#'
export REZ_WRAPPER_ALIAS='#ALIAS#'

source $REZ_PATH/init.sh

if [ "#RCFILE#" != "" ]; then
	path=#RCFILE#
	if [ "`echo '#RCFILE#' | grep '^/'`" == "" ]; then
		path=`dirname $0`/#RCFILE#
	fi
	if [ -e $path ]; then
		export __REZ_RCFILE=$path
	fi
fi

if [ "${!#}" == "---i" ]; then
	export REZ_ENV_PROMPT="${REZ_ENV_PROMPT}#CONTEXTNAME#>"
	/bin/bash --rcfile $REZ_PATH/bin/rez-env-bashrc
	exit $?
fi

source $REZ_WRAPPER_CONTEXT
unset REZ_WRAPPER_CONTEXT

if [ "$__REZ_RCFILE" != "" ]; then
	source $__REZ_RCFILE
fi

if [ "${!#}" == "---s" ]; then
	if [ -f ~/.bashrc ]; then
		source ~/.bashrc &> /dev/null
	fi
	/bin/bash -s
	exit $?
else
	if [ -f ~/.bashrc ]; then
		source ~/.bashrc &> /dev/null
	fi
	#ALIAS# $*
	exit $?
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
