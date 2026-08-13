DESCRIPTION = "Aos systemd target"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://aos.target \
    file://aoscore.env \
    file://aoscore-benchmark.env \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "aos.target"

FILES:${PN} = " \
    ${systemd_system_unitdir} \
    ${sysconfdir} \
"

CONFFILES:${PN} += " \
    ${sysconfdir}/default/aoscore.env \
"

do_install() {
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${S}/aos.target ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/default
    if ${@bb.utils.contains('DISTRO_FEATURES', 'benchmark', 'true', 'false', d)}; then
        install -m 0644 ${S}/aoscore-benchmark.env ${D}${sysconfdir}/default/aoscore.env
    else
        install -m 0644 ${S}/aoscore.env ${D}${sysconfdir}/default/aoscore.env
    fi
}
