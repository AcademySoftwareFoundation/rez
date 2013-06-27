#! /bin/bash

DIR=$(dirname $(readlink -f $BASH_SOURCE[0]))
rez_release_version=$( echo $(grep rez_version "$DIR/version.sh") | sed -r s/rez_version=\'\(.*\)\'/\\1/ )
echo "Found version: $rez_release_version in $DIR/version.sh"

sudo mkdir -pv /tools/shed/opensource/la-rez/${rez_release_version}/payload

tmp_loc=$(mktemp -d)

cd $tmp_loc
if [[ "$@" != '' ]]; then
    echo "Using overridden repo (branch?) instead of 'chili-git:la-rez': $@"
    git clone -v $@ la-rez
else
    git clone -v chili-git:la-rez
fi
sudo mv la-rez /tools/shed/opensource/la-rez/${rez_release_version}/src

cd /tools/shed/opensource/la-rez/${rez_release_version}/src

sudo ./configure_methodsm_python2_7_3.sh
sudo ./configure_methodsm_python2_6_8.sh
# rez is not 100% 2.5 compatible
# sudo ./configure_methodsm_python2_5_6.sh

sudo ./install.sh /tools/shed/opensource/la-rez/${rez_release_version}/payload

