#!/bin/bash
#
# This script:
# 1. Takes the content from here: https://github.com/nerdvegas/rez-wiki;
# 2. Then writes it into a local clone of https://github.com/nerdvegas/rez.wiki.git;
# 3. Then follows the procedure outlined in README from 2.
#
# This process exists because GitHub does not support contributions to wiki
# repositories - this is a workaround.
#
set -e

rm -rf .rez-gen-wiki-tmp
mkdir .rez-gen-wiki-tmp
cd .rez-gen-wiki-tmp

git clone git@github.com:nerdvegas/rez.git
git clone git@github.com:nerdvegas/rez-wiki.git
git clone git@github.com:nerdvegas/rez.wiki.git

cp -f ./rez-wiki/pages/* ./rez.wiki/pages/
cp -rf ./rez-wiki/media/* ./rez.wiki/media/
export REZ_SOURCE_DIR=$(pwd)/rez

cd ./rez.wiki
python ./utils/process.py
bash ./utils/update.sh

rm -rf .rez-gen-wiki-tmp
