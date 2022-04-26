DESCRIPTION = "Aos provisioning firewall"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://provfirewall.sh \
    file://aos-provfirewall.service \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE_${PN} = "aos-provfirewall.service"

FILES_${PN} = " \
    ${systemd_system_unitdir} \
    ${aos_opt_dir} \
"

do_install() {
    install -d ${D}${aos_opt_dir}
    install -m 0755 ${S}/provfirewall.sh ${D}${aos_opt_dir}

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${S}/aos-provfirewall.service ${D}${systemd_system_unitdir}
}
