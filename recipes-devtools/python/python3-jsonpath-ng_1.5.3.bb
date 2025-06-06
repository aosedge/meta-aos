SUMMARY = "A final implementation of JSONPath for Python that aims to be standard compliant, including arithmetic and binary comparison operators and providing clear AST for metaprogramming."
HOMEPAGE = "https://github.com/h2non/jsonpath-ng"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

PYPI_PACKAGE = "jsonpath-ng"

SRC_URI[sha256sum] = "a273b182a82c1256daab86a313b937059261b5c5f8c4fa3fc38b882b344dd567"

inherit pypi setuptools3

RDEPENDS:${PN} += " \
    python3-ply \
    python3-six \
"
