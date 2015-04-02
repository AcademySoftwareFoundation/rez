
_rez_complete_fn()
{
    COMPREPLY=($(COMP_LINE=${COMP_LINE} COMP_POINT=${COMP_POINT} _rez-complete))
}

complete -F _rez_complete_fn rez
complete -F _rez_complete_fn rezolve
complete -F _rez_complete_fn rez-bind
complete -F _rez_complete_fn rez-build
complete -F _rez_complete_fn rez-config
complete -F _rez_complete_fn rez-context
complete -F _rez_complete_fn rez-plugins
complete -F _rez_complete_fn rez-env
complete -F _rez_complete_fn rez-help
complete -F _rez_complete_fn rez-interpret
complete -F _rez_complete_fn rez-release
complete -F _rez_complete_fn rez-search
complete -F _rez_complete_fn rez-view
complete -F _rez_complete_fn rez-suite
complete -F _rez_complete_fn rez-selftest
