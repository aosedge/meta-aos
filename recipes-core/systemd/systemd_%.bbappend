FILESEXTRAPATHS:prepend := "${THISDIR}/systemd:"

SRC_URI += " \
    file://systemd-journal-flush-override.conf \
    ${@bb.utils.contains('LAYERSERIES_CORENAMES', 'dunfell', 'file://0001-systemd-networkd.socket-Add-conflict-with-shutdown.t.patch', '', d)} \
"

do_install:append() {
    install -d ${D}${sysconfdir}/systemd/system/systemd-journal-flush.service.d
    install -m 0644 ${WORKDIR}/systemd-journal-flush-override.conf ${D}${sysconfdir}/systemd/system/systemd-journal-flush.service.d
}
