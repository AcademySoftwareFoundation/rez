#! /bin/bash

rez_release_version=1.6.13
tmp_loc=$(mktemp)

git clone chili-git:la-rez $tmp_loc

sudo mkdir -p /tools/shed/opensource/la-rez/${rez_release_version}/payload

sudo mv $tmp_loc /tools/shed/opensource/la-rez/${rez_release_version}/src

cd /tools/shed/opensource/la-rez/${rez_release_version}/src

sudo ./configure_methodsm_python2_7_3.sh
sudo ./configure_methodsm_python2_6_8.sh
# rez is not 100% 2.5 compatible
# sudo ./configure_methodsm_python2_5_6.sh

sudo ./install.sh /tools/shed/opensource/la-rez/${rez_release_version}/payload

