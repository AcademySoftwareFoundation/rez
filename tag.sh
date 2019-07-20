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
out=$(git tag $version 2>&1)

if [ $? -ne 0 ]; then
    test=$(echo ${out} | grep 'already exists')
    if [ "$test" == "" ]; then
        echo ${out}
        exit 1
    else
        echo "(tag already exists)"
    fi
fi

if [ ! -z "$push" ]; then
    echo "pushing tag..."
    git push origin $version
fi
