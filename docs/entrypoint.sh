#!/bin/bash

set -euf -x -o pipefail

CONTAINER_HOSTNAME="rez-sphinx-build"
if [ "${HOSTNAME}" != "${CONTAINER_HOSTNAME}" ]
then
    THIS_FILE="$(readlink -f ${BASH_SOURCE[0]})"
    ROOT_DIR="$(dirname $(dirname $THIS_FILE))"
    PY_VERSION="${PY_VERSION:-$(
        (python --version 2>&1 || echo 2.7) | grep -oP '\d+\.\d+'
    )}"

    declare -a RUN_FLAGS
    [ -t 1 ] && RUN_FLAGS=("-i" "--tty") || RUN_FLAGS=("-i")
    # RUN_FLAGS+=("--rm")
    RUN_FLAGS+=("--hostname" "${CONTAINER_HOSTNAME}")
    RUN_FLAGS+=("--volume" "${ROOT_DIR}:${ROOT_DIR}")
    RUN_FLAGS+=("--workdir" "${ROOT_DIR}")
    RUN_FLAGS+=("--entrypoint" "/bin/bash")
    RUN_FLAGS+=("--user" "$(stat -c '%u:%g' $THIS_FILE)")

    # Script will exit after running docker run ...
    exec docker run "${RUN_FLAGS[@]}" "python:${PY_VERSION}" "${THIS_FILE}"
fi

# ...therefore, the remaining from now will be run inside Docker container
if [ "$HOME" == "/" ] 
then
    # Fake user's $HOME in container to fix permission issues
    export HOME="/tmp/tmp.ohi3VYj23H" # "$(mktemp -d)"
fi

# Install dependencies and build docs
export PATH="${PATH}:${HOME}/.local/bin"
pip install --user sphinx-argparse sphinx_rtd_theme .
exec sphinx-build docs/ docs/_build