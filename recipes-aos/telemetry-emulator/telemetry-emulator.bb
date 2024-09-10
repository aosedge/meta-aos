DESCRIPTION = "AOS Telemetry Emulator"

DIR_TELEMETRY_EMULATOR = "${datadir}/telemetry_emulator"

LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"

BRANCH = "main"
SRCREV = "${AUTOREV}"

SRC_URI = " \
    git://github.com/aosedge/telemetry_emulator.git;protocol=https;branch=${BRANCH} \
    file://telemetry-emulator.service \
"

S = "${WORKDIR}/git"

RDEPENDS:${PN} = " \
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

FILES:${PN} = " \
    ${DIR_TELEMETRY_EMULATOR}/*.py \
    ${DIR_TELEMETRY_EMULATOR}/*.json \
"

do_install() {
    install -d ${D}${DIR_TELEMETRY_EMULATOR}
    install -m 0644 ${S}/*.py ${D}${DIR_TELEMETRY_EMULATOR}
    install -m 0644 ${S}/*.json ${D}${DIR_TELEMETRY_EMULATOR}
}

inherit systemd

SYSTEMD_SERVICE:${PN} = "telemetry-emulator.service"

FILES:${PN} += "${systemd_system_unitdir}/telemetry-emulator.service"

do_install:append() {
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/*.service ${D}${systemd_system_unitdir}
}
