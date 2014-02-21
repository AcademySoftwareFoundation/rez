_software_packages()
{
    local cur prev fam entries
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    fam=''
    entries=''
    if [[ ${cur} == *-* ]] ; then
    	fam=`echo $cur | sed 's/-.*//g'`
    else
    	for path in `echo $REZ_PACKAGES_PATH | /usr/bin/tr ':' ' '`
		do
			if [ -d $path ]; then
				fam=`echo $fam ; /bin/ls $path | grep "^$cur"`
			fi
		done

		fam=`echo $fam | /usr/bin/tr ' ' '\n' | sort -u`
    fi

    if [ `echo $fam | /usr/bin/wc -w` -eq 1 ]; then
    	entries=$fam
		for path in `echo $REZ_PACKAGES_PATH | /usr/bin/tr ':' ' '`
		do
			if [ -d $path/$fam ]; then
			    if [ `uname` == 'Linux' ]; then
				    entries=`echo $entries ; /usr/bin/find $path/$fam -mindepth 2 -maxdepth 2 -name package.yaml -exec dirname {} \; | tr '/' ' ' | awk '{print "'$fam'-"$NF}'`
                else
                    # FIXME this incorrectly gives non-pkg-subdirs as completion options
			        entries=`echo $entries ; /bin/ls $path/$fam | /usr/bin/tr ' ' '\n' | grep -v 'package.uuid' | awk '{print "'$fam'-"$1}'`
			    fi
			fi
		done
    else
    	entries=$fam
    fi

    COMPREPLY=( $(compgen -W "${entries}" -- ${cur}) )
    return 0
}

complete -F _software_packages rez
complete -F _software_packages rez-config
complete -F _software_packages rez-env
complete -F _software_packages rez-help
complete -F _software_packages rez-which
complete -F _software_packages rez-run
complete -F _software_packages rez-depends
complete -F _software_packages rez-diff
complete -F _software_packages rez-info






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
