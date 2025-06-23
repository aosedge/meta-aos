SUMMARY = "Powerful and Lightweight Python Tree Data Structure"
HOMEPAGE = "https://github.com/c0fec0de/anytree"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=e3fc50a88d0a364313df4b21ef20c29e"

PYPI_PACKAGE = "anytree"

SRC_URI[sha256sum] = "e02af617d41ede47f922e5deea0e4efc3201c6e7330cfc1265409762e5381283"

inherit pypi python_poetry_core

RDEPENDS:${PN} += " \
    python3-six \
"

BBCLASSEXTEND += "native nativesdk"
