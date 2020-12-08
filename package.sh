#!/bin/bash -e

version=$(grep '"version"' manifest.json | cut -d: -f2 | cut -d\" -f2)

# Setup environment for building inside Dockerized toolchain
[ $(id -u) = 0 ] && umask 0

# Clean up from previous releases
rm -rf *.tgz *.sha256sum package SHA256SUMS

if [ -z "${ADDON_ARCH}" ]; then
  TARFILE_SUFFIX=
else
  PYTHON_VERSION="$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d. -f 1-2)"
  TARFILE_SUFFIX="-${ADDON_ARCH}-v${PYTHON_VERSION}"
fi


# Prep new package
mkdir package

# Put package together
cp -r pkg LICENSE manifest.json *.py README.md package/
find package -type f -name '*.pyc' -delete
find package -type f -name '._*' -delete
find package -type d -empty -delete

echo "generating checksums"
cd package
find . -type f \! -name SHA256SUMS -exec shasum --algorithm 256 {} \; >> SHA256SUMS
cd -

echo "creating archive"
TARFILE="internet-radio-${version}.tgz"
tar czf ${TARFILE} package

shasum --algorithm 256 ${TARFILE} > ${TARFILE}.sha256sum


#rm -rf SHA256SUMS package
#sha256sum "internet-radio-${version}.tgz"

tar czf "internet-radio-${version}.tgz" package
cat ${TARFILE}.sha256sum
#sha256sum "internet-radio-${version}.tgz"
