FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI += "\
    file://journald_persist.conf \
"

FILES:${PN} += " \
    ${sysconfdir} \
"

do_install:append() {
    install -D -m0644 ${WORKDIR}/journald_persist.conf ${D}${systemd_unitdir}/journald.conf.d/10-${PN}.conf
}
