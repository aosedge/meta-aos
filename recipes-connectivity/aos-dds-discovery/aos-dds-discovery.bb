FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SUMMARY = "Fast DDS discovery server service"
DESCRIPTION = "Runs the Fast DDS discovery server on the node, outside the \
service network segments, so that services in different segments can discover \
each other over unicast without multicast."

LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"

SRC_URI = "file://aos-dds-discovery.service"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "aos-dds-discovery.service"
SYSTEMD_AUTO_ENABLE = "enable"

RDEPENDS:${PN} = "fastdds-tools"

do_install() {
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-dds-discovery.service ${D}${systemd_system_unitdir}/

    sed -i \
        -e "s|@SYSCONFDIR@|${sysconfdir}|g" \
        -e "s|@BINDIR@|${bindir}|g" \
        ${D}${systemd_system_unitdir}/aos-dds-discovery.service
}

FILES:${PN} = "${systemd_system_unitdir}"
