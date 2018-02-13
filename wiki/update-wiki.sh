#!/bin/bash
#
# This script:
# 1. Takes the content from this repo;
# 2. Then writes it into a local clone of https://github.com/nerdvegas/rez.wiki.git;
# 3. Then follows the procedure outlined in README from 2.
#
# This process exists because GitHub does not support contributions to wiki
# repositories - this is a workaround.
#
set -ex

rm -rf .rez-gen-wiki-tmp
mkdir .rez-gen-wiki-tmp
cd .rez-gen-wiki-tmp

git clone git@github.com:nerdvegas/rez.wiki.git

cp -f ../pages/* ./rez.wiki/pages/
cp -rf ../media/* ./rez.wiki/media/

# rez.wiki scripts need this var set to extract some docs from rez source
export REZ_SOURCE_DIR=$(pwd)/../../

cd ./rez.wiki
python ./utils/process.py
bash ./utils/update.sh

cd ../../
rm -rf .rez-gen-wiki-tmp
