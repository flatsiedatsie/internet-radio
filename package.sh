#!/bin/bash

set -e

version=$(grep version package.json | cut -d: -f2 | cut -d\" -f2)

# Clean up from previous releases
rm -rf *.tgz package
rm -f SHA256SUMS
rm -rf lib

# Put package together
mkdir package
mkdir lib

# Pull down Python dependencies
pip3 install -r requirements.txt -t lib --no-binary python-vlc --prefix ""

cp -r pkg lib LICENSE package.json *.py requirements.txt setup.cfg install_vlc.sh package/
find package -type f -name '*.pyc' -delete
find package -type d -empty -delete

# Generate checksums
cd package
sha256sum *.py pkg/*.py LICENSE install_vlc.sh requirements.txt setup.cfg > SHA256SUMS
cd -

# Make the tarball
tar czf "internet-radio-${version}.tgz" package
sha256sum "internet-radio-${version}.tgz"
#sudo systemctl restart mozilla-iot-gateway.service
