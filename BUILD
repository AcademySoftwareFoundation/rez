rez_release_version=1.6.11

git clone chili-git:la-rez /tmp/rez-${rez_release_version}

sudo mkdir -p /tools/shed/opensource/la-rez/${rez_release_version}/payload

sudo mv /tmp/rez-${rez_release_version} /tools/shed/opensource/la-rez/${rez_release_version}/src

cd /tools/shed/opensource/la-rez/${rez_release_version}/src

sudo ./configure_methodsm_python2_5_6.sh
sudo ./configure_methodsm_python2_6_8.sh
sudo ./configure_methodsm_python2_7_3.sh

sudo ./install.sh /tools/shed/opensource/la-rez/${rez_release_version}/payload

