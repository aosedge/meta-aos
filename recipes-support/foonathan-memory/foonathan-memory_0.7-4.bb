SUMMARY = "STL compatible C++ memory allocator library"
DESCRIPTION = "Memory allocator library used by eProsima Fast DDS."
HOMEPAGE = "https://github.com/foonathan/memory"

LICENSE = "Zlib"
LIC_FILES_CHKSUM = "file://LICENSE;md5=858ac481b3e933be38e4d36cb0dfcee8"

SRC_URI = "git://github.com/foonathan/memory.git;protocol=https;nobranch=1"
SRCREV = "79d054caaa491d9b6ed7cc65a3a84b495578e6c1"

S = "${WORKDIR}/git"

inherit cmake

EXTRA_OECMAKE = " \
    -DBUILD_SHARED_LIBS=ON \
    -DFOONATHAN_MEMORY_BUILD_EXAMPLES=OFF \
    -DFOONATHAN_MEMORY_BUILD_TESTS=OFF \
    -DFOONATHAN_MEMORY_BUILD_TOOLS=OFF \
"

SOLIBS = "-*.so"
FILES_SOLIBSDEV = ""

FILES:${PN}-dev += " \
    ${libdir}/foonathan_memory \
    ${includedir}/foonathan_memory \
"

FILES:${PN}-doc += "${datadir}/foonathan_memory"

BBCLASSEXTEND = "native nativesdk"
