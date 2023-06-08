DESCRIPTION = "Aos systemd target"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://aos.target \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "aos.target"

FILES:${PN} = " \
    ${systemd_system_unitdir} \
"

do_install() {
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${S}/aos.target ${D}${systemd_system_unitdir}
}
