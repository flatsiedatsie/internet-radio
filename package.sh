#!/bin/bash -e

version=$(grep '"version":' manifest.json | cut -d: -f2 | cut -d\" -f2)

# Clean up from previous releases
rm -rf *.tgz package SHA256SUMS lib

# Prep new package
mkdir lib package

# Pull down Python dependencies
pip3 install -r requirements.txt -t lib --no-binary requests --prefix ""

# Put package together
cp -r lib pkg LICENSE manifest.json *.py README.md package/
find package -type f -name '*.pyc' -delete
find package -type d -empty -delete

# Generate checksums
#cd package
#find . -type f \! -name SHA256SUMS -exec shasum --algorithm 256 {} \; >> SHA256SUMS
#cd -

cd package
find . -type f \! -name SHA256SUMS -exec sha256sum {} \; >> SHA256SUMS
cd ..

# Make the tarball
#TARFILE="internet-radio-${version}.tgz"
#tar czf ${TARFILE} package

#shasum --algorithm 256 ${TARFILE} > ${TARFILE}.sha256sum

#rm -rf SHA256SUMS package
#sha256sum "internet-radio-${version}.tgz"

tar czf "internet-radio-${version}.tgz" package
sha256sum "internet-radio-${version}.tgz"