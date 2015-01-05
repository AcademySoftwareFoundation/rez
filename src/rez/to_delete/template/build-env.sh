#!/bin/bash

# because of how cmake works, you must cd into same dir as script to run it
if [ "./build-env.sh" != "$0" ] ; then
    echo "you must cd into the same directory as this script to use it." >&2
    exit 1
fi

source %(env_bake_file)s
export REZ_CONTEXT_FILE=%(env_bake_file)s
env > %(actual_bake)s
