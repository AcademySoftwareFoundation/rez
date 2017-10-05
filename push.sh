#!/bin/bash
#
# Pushes the repo to github; also creates and pushes version tag, if branch is
# master and user is nerdvegas. If you aren't nerdvegas, please don't change
# this file.
#

branch=$(git rev-parse --abbrev-ref HEAD)

# just push if not master
if [ "$branch" != "master" ]; then
    echo "pushing non-master branch..."
    git push
    exit
fi

# just push if not nerdvegas
git remote -vv | grep -w origin | grep -w nerdvegas > /dev/null
if [ $? -ne 0 ]; then
    echo "pushing, not nerdvegas..."
    git push
    exit
fi

# tag version
version=$(cat src/rez/utils/_version.py | grep -w _rez_version | head -n1 | tr '"' ' ' | awk '{print $NF}')
echo "tagging ${version}..."
git tag $version
if [ $? -ne 0 ]; then
    exit 1
fi

# push
git push
if [ $? -eq 0 ]; then
    git push --tags
fi
