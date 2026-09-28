SUMMARY = "eProsima Fast CDR serialization library"
DESCRIPTION = "Serialization library implementing the CDR standard, required by Fast DDS."
HOMEPAGE = "https://github.com/eProsima/Fast-CDR"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

SRC_URI = "git://github.com/eProsima/Fast-CDR.git;protocol=https;nobranch=1"
SRCREV = "d5906d720193175e898df569c8531b095648e668"

S = "${WORKDIR}/git"

inherit cmake

EXTRA_OECMAKE = " \
    -DBUILD_SHARED_LIBS=ON \
    -DBUILD_TESTING=OFF \
"

BBCLASSEXTEND = "native nativesdk"
