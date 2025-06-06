DESCRIPTION = "Vehicle Signal Specification"
LICENSE = "MPL-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=9741c346eef56131163e13b9db1241b3"

BRANCH = "release/5.0"
SRCREV = "f23ba53be78a8bf2b8df2496bbfccb2860913892"

SRC_URI = "git://github.com/COVESA/vehicle_signal_specification.git;branch=${BRANCH};protocol=https"

S = "${WORKDIR}/git"

UPSTREAM_CHECK_GITTAGREGEX = "v(?P<pver>\d+(\.\d+)+)"

inherit allarch update-alternatives

DEPENDS = "vss-tools-native"

EXTRA_OEMAKE = "TOOLSDIR=${STAGING_BINDIR_NATIVE}"

FILES:${PN} += " \
    ${datadir} \
"

do_configure[noexec] = "1"

do_compile() {
    oe_runmake json
}

do_install() {
    # Cannot use the "install" target in the project Makefile, as it is
    # intended for setting the repo up for builds.
    # For now, just the generated JSON is installed. It is possible that
    # installing the vspec files somewhere as a development package may
    # be useful, but for now things will be kept simple.
    install -d ${D}${datadir}/vss
    install -m 0644 ${S}/vss.json ${D}${datadir}/vss/vss.json
    install -m 0644 ${S}/vss.json ${D}${datadir}/vss/vss-test.json
}
