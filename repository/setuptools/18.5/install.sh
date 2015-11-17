#!/bin/bash

srcpath=$1
destpath=$2

pyver="${REZ_PYTHON_MAJOR_VERSION}.${REZ_PYTHON_MINOR_VERSION}"
pypath=${destpath}/lib/python${pyver}/site-packages
mkdir -p ${pypath} &> /dev/null

cd ${srcpath}
PYTHONPATH=$PYTHONPATH:${pypath} python setup.py install --prefix=${destpath} --old-and-unmanageable

mkdir -p ${destpath}/python &> /dev/null
cp -rf ${pypath}/* ${destpath}/python/
rm -rf ${destpath}/lib
