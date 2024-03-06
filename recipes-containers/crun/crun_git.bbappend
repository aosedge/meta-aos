LIC_FILES_CHKSUM = "file://COPYING;md5=b234ee4d69f5fce4486a80fdaf4a4263"

SRCREV_crun = "1961d211ba98f532ea52d2e80f4c20359f241a98"
SRCREV_libocispec = "19c05670c37a42c217caa7b141bcaada7867cc15"
SRCREV_ispec = "0b40f0f367c396cc5a7d6a2e8c8842271d3d3844"
SRCREV_rspec = "55ae2744e3a034668fa2c40687251095a69ed63e"
SRCREV_yajl = "49923ccb2143e36850bcdeb781e2bcdf5ce22f15"

SRC_URI = " \
    git://github.com/containers/crun.git;branch=main;name=crun;protocol=https \
    git://github.com/containers/libocispec.git;branch=main;name=libocispec;destsuffix=git/libocispec;protocol=https \
    git://github.com/opencontainers/runtime-spec.git;branch=main;name=rspec;destsuffix=git/libocispec/runtime-spec;protocol=https \
    git://github.com/opencontainers/image-spec.git;branch=main;name=ispec;destsuffix=git/libocispec/image-spec;protocol=https \
    git://github.com/containers/yajl.git;branch=main;name=yajl;destsuffix=git/libocispec/yajl;protocol=https \
"

PV = "1.8.3+git${SRCREV_crun}"

DEPENDS += "m4-native systemd"

do_configure:prepend () {
    # extracted from autogen.sh in crun source. This avoids
    # git submodule fetching.
    mkdir -p m4
    autoreconf -fi
}
