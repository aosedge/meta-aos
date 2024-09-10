DESCRIPTION = "AOS Python VIS Client"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

BRANCH = "master"
SRCREV = "${AUTOREV}"

SRC_URI = "git://github.com/aosedge/libvis.git;branch=${BRANCH};protocol=https"

S = "${WORKDIR}/git"

inherit setuptools3
