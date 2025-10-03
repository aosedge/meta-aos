DESCRIPTION = "AOS Python VIS Client"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

BRANCH = "master"
SRCREV = "fb98d008e95b441b3d0185386f715b0b27849e06"

SRC_URI = "git://github.com/aosedge/libvis.git;branch=${BRANCH};protocol=https"

S = "${WORKDIR}/git"

inherit setuptools3
