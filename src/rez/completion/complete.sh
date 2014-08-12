
_rez_complete_fn()
{
    COMPREPLY=( $(COMP_LINE=${COMP_LINE} COMP_POINT=${COMP_POINT} _rez-complete) )
}

complete -F _rez_complete_fn rez
complete -F _rez_complete_fn rezolve
complete -F _rez_complete_fn rez-bind
complete -F _rez_complete_fn rez-build
complete -F _rez_complete_fn rez-config
complete -F _rez_complete_fn rez-context
complete -F _rez_complete_fn rez-env
complete -F _rez_complete_fn rez-help
complete -F _rez_complete_fn rez-interpret
complete -F _rez_complete_fn rez-release
complete -F _rez_complete_fn rez-search
complete -F _rez_complete_fn rez-suite
complete -F _rez_complete_fn rez-test
complete -F _rez_complete_fn rez-tools



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
