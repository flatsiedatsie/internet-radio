#!/bin/bash -e

version=$(grep '"version":' manifest.json | cut -d: -f2 | cut -d\" -f2)

# Clean up from previous releases
rm -rf *.tgz package SHA256SUMS

# Prep new package
mkdir package

# Put package together
cp -r pkg LICENSE package.json manifest.json *.py README.md package/
find package -type f -name '*.pyc' -delete
find package -type d -empty -delete

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
