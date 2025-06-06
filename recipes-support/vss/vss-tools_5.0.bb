DESCRIPTION = "COVESA Vehicle Signal Specification tools"
LICENSE = "MPL-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=9741c346eef56131163e13b9db1241b3"

BRANCH = "release/5.0"
SRCREV = "9ba7f40c0995358a293aab729d57739c3e9b2829"

SRC_URI = "git://github.com/COVESA/vss-tools.git;protocol=https;branch=${BRANCH} "

S = "${WORKDIR}/git"

inherit python_poetry_core

RDEPENDS:${PN} += " \
    python3-core \
    python3-ctypes \
    python3-email \
    python3-importlib-metadata \
    python3-json \
    python3-logging \
    python3-netclient \
    python3-pkg-resources \
    python3-anytree \
    python3-deprecation \
    python3-graphql-core \
    python3-pyyaml \
    python3-six \
    python3-pydantic \
    python3-rich-click \
"

BBCLASSEXTEND += "native nativesdk"
