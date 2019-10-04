
_rez_complete_fn()
{
    COMPREPLY=($(COMP_LINE=${COMP_LINE} COMP_POINT=${COMP_POINT} _rez-complete))
}

compctl -K _rez_complete_fn rez
compctl -K _rez_complete_fn rezolve
compctl -K _rez_complete_fn rez-bind
compctl -K _rez_complete_fn rez-build
compctl -K _rez_complete_fn rez-config
compctl -K _rez_complete_fn rez-context
compctl -K _rez_complete_fn rez-plugins
compctl -K _rez_complete_fn rez-env
compctl -K _rez_complete_fn rez-help
compctl -K _rez_complete_fn rez-interpret
compctl -K _rez_complete_fn rez-release
compctl -K _rez_complete_fn rez-search
compctl -K _rez_complete_fn rez-view
compctl -K _rez_complete_fn rez-suite
compctl -K _rez_complete_fn rez-selftest
