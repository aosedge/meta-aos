DESCRIPTION = "AOS Telemetry Emulator"

DIR_TELEMETRY_EMULATOR = "${datadir}/telemetry_emulator"

BRANCH = "main"
SRCREV = "b96983140289e617b3d54f9a92040107bbaaf58b"
SRC_URI = " \
    git://git@github.com/aoscloud/telemetry_emulator;protocol=ssh;branch=${BRANCH} \
    file://telemetry-emulator.service \
"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"

S = "${WORKDIR}/git"

RDEPENDS_${PN} = " \
    python3 \
    python3-core \
    python3-compression \
    python3-datetime \
    python3-json \
    python3-misc \
    python3-netserver \
    python3-shell \
    python3-threading \
"

FILES_${PN} = " \
    ${DIR_TELEMETRY_EMULATOR}/*.py \
    ${DIR_TELEMETRY_EMULATOR}/*.json \
"

do_install() {
    install -d ${D}${DIR_TELEMETRY_EMULATOR}
    install -m 0644 ${S}/*.py ${D}${DIR_TELEMETRY_EMULATOR}
    install -m 0644 ${S}/*.json ${D}${DIR_TELEMETRY_EMULATOR}
}

inherit systemd

SYSTEMD_SERVICE_${PN} = "telemetry-emulator.service"

FILES_${PN} += "${systemd_system_unitdir}/telemetry-emulator.service"

do_install_append() {
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/*.service ${D}${systemd_system_unitdir}
}
