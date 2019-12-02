#!/bin/bash

version=$(grep '"version":' manifest.json | cut -d: -f2 | cut -d\" -f2)


# Clean up from previous releases
rm -rf *.tgz package
rm -f SHA256SUMS
rm -rf lib

# Put package together
mkdir package
mkdir lib

# Pull down Python dependencies
pip3 install -r requirements.txt -t lib --no-binary requests --prefix ""


cp *.py *.json requirements.txt setup.cfg LICENSE README.md package/
cp -r lib pkg package/
find package -type f -name '*.pyc' -delete
find package -type d -empty -delete

cd package
find . -type f \! -name SHA256SUMS -exec sha256sum {} \; >> SHA256SUMS
cd ..

tar czf "internet-radio-${version}.tgz" package
sha256sum "internet-radio-${version}.tgz"
