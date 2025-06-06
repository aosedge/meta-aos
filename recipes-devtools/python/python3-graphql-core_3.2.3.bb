SUMMARY = "GraphQL implementation for Python"
HOMEPAGE = "https://github.com/graphql-python/graphql-core"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=73706fb002de2debc52328afd1688817"

PYPI_PACKAGE = "graphql-core"

SRC_URI[sha256sum] = "06d2aad0ac723e35b1cb47885d3e5c45e956a53bc1b209a9fc5369007fe46676"

inherit pypi setuptools3

BBCLASSEXTEND += "native nativesdk"
