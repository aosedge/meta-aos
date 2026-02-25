FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI += " \
    file://rpc-rquotad.service \
"

inherit systemd

SYSTEMD_SERVICE:${PN} = "rpc-rquotad.service"

FILES:${PN} += "${systemd_system_unitdir}/rpc-rquotad.service"

do_install:append() {
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/rpc-rquotad.service ${D}${systemd_system_unitdir}
}
