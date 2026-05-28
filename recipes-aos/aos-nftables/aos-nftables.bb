DESCRIPTION = "Aos base nftables ruleset (fail-closed forward default-drop)"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://aos.nft \
    file://aos-nftables.service \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "aos-nftables.service"

FILES:${PN} = " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
"

RDEPENDS:${PN} += " \
    nftables \
"

RRECOMMENDS:${PN} += " \
    kernel-module-nf-conntrack \
    kernel-module-nft-ct \
"

do_install() {
    install -d ${D}${sysconfdir}/nftables
    install -m 0644 ${WORKDIR}/aos.nft ${D}${sysconfdir}/nftables/aos.nft

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-nftables.service ${D}${systemd_system_unitdir}
}
