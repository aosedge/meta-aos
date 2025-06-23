SUMMARY = "Use git repo data for building a version number according PEP-440"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=f22e7cb81b49604c2450680982bdc067"
PYPI_PACKAGE = "setuptools-git-versioning"

DEPENDS = "python3-six-native"

SRC_URI[sha256sum] = "be2901afcb7c865e3b500a38183598657fd029a1a72c8d1dfc7fbffb5c227dac"

inherit pypi setuptools3

RDEPENDS:${PN} += " \
    python3-setuptools \
    python3-six \
"

BBCLASSEXTEND = "native"
