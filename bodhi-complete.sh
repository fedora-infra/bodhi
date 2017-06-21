_bodhi_completion() {
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \
                   COMP_CWORD=$COMP_CWORD \
                   _BODHI_COMPLETE=complete $1 ) )
    return 0
}

complete -F _bodhi_completion -o default bodhi;
