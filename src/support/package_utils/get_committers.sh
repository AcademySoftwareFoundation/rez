#!/bin/bash
#
# Prints a list of users who have committed to the repo in cwd, in decreasing
# order of commit count.
#
# Supports:
# * git
#
set -e

# git
git status &> /dev/null
if [ $? -eq 0 ]; then
    git shortlog -sn | cut -f2
    exit 0
fi
