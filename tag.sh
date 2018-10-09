#!/bin/bash
#
# Tag git repo with current version as defined in source.
#
push=

while getopts p opt
do
    case $opt in
    p) push=1;;
    ?) printf "Usage: %s: [-p]\n" $0
       exit 2;;
    esac
done

version=$(cat src/rez/utils/_version.py | grep -w _rez_version | head -n1 | tr '"' ' ' | awk '{print $NF}')
echo "tagging ${version}..."
git tag $version
if [ $? -ne 0 ]; then
    exit 1
fi

if [ ! -z "$push" ]; then
    echo "pushing tags..."
    git push --tags
fi
