SUMMARY = "eProsima Fast DDS"
DESCRIPTION = "C++ implementation of the OMG DDS specification and the RTPS wire protocol."
HOMEPAGE = "https://github.com/eProsima/Fast-DDS"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

SRC_URI = "git://github.com/eProsima/Fast-DDS.git;protocol=https;nobranch=1"
SRCREV = "39303846fb8534ef69fa65f9fa4bcc9e6a7c995a"

S = "${WORKDIR}/git"

DEPENDS = "fastcdr foonathan-memory asio libtinyxml2 openssl"

inherit cmake

EXTRA_OECMAKE = " \
    -DBUILD_SHARED_LIBS=ON \
    -DTHIRDPARTY=OFF \
    -DCOMPILE_TOOLS=ON \
    -DSECURITY=ON \
    -DCOMPILE_EXAMPLES=OFF \
    -DINSTALL_EXAMPLES=OFF \
    -DBUILD_TESTING=OFF \
    -DEPROSIMA_BUILD=OFF \
"

PACKAGES =+ "${PN}-tools"
FILES:${PN}-tools = " \
    ${bindir} \
    ${prefix}/tools \
"
RDEPENDS:${PN}-tools = "${PN} python3-core python3-psutil"

BBCLASSEXTEND = "native nativesdk"
