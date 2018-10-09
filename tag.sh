#!/bin/bash
#
# Tag git repo with current version as defined in source.
#
version=$(cat src/rez/utils/_version.py | grep -w _rez_version | head -n1 | tr '"' ' ' | awk '{print $NF}')
echo "tagging ${version}..."
git tag $version
if [ $? -ne 0 ]; then
    exit 1
fi
