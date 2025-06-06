DESCRIPTION  = "KUKSA.val databroker, the KUKSA Vehicle Abstraction Layer"

SUMMARY = "KUKSA.val databroker, the KUKSA Vehicle Abstraction Layer"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

BRANCH = "main"
SRCREV = "30e5c13abc496d0b39aaa6c25acebb088b9902e3"

SRC_URI = "git://github.com/eclipse-kuksa/kuksa-databroker.git;protocol=https;branch=${BRANCH}"

SRC_URI += " \
    file://0001-Remove-protobuf-src-usage.patch \
    file://kuksa-databroker.service \
    file://kuksa-databroker.env \
    file://CA.pem \
    file://Client.key \
    file://Client.pem \
    file://Server.key \
    file://Server.pem \
    file://jwt.key.pub \
"

S = "${WORKDIR}/git"

inherit cargo cargo-update-recipe-crates systemd 

DEPENDS = "protobuf-native grpc-native"

CARGO_BUILD_FLAGS += "--features viss"

SYSTEMD_SERVICE:${PN} = "kuksa-databroker.service"

FILES:${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
"

require kuksa-databroker-crates.inc

do_install:append() {
    install -d ${D}${sysconfdir}/default
    install -m 0644 ${WORKDIR}/kuksa-databroker.env ${D}${sysconfdir}/default/kuksa-databroker

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/kuksa-databroker.service ${D}${systemd_system_unitdir}


    install -d ${D}${sysconfdir}/kuksa-val
    install -m 0644 ${WORKDIR}/CA.pem ${D}${sysconfdir}/kuksa-val

    install -m 0644 ${WORKDIR}/Server.key ${D}${sysconfdir}/kuksa-val
    install -m 0644 ${WORKDIR}/Server.pem ${D}${sysconfdir}/kuksa-val
    install -m 0644 ${WORKDIR}/jwt.key.pub ${D}${sysconfdir}/kuksa-val
    install -m 0644 ${WORKDIR}/Client.key ${D}${sysconfdir}/kuksa-val
    install -m 0644 ${WORKDIR}/Client.pem ${D}${sysconfdir}/kuksa-val
}

# The upstream Cargo.toml builds optimized and stripped binaries, for
# now disable the QA check as opposed to tweaking the configuration.
INSANE_SKIP:${PN} = "already-stripped"
INSANE_SKIP:${PN}-cli = "already-stripped"

RDEPENDS:${PN} += "vss"
