FILESEXTRAPATHS_prepend := "${THISDIR}/systemd:"

SRC_URI += "\
    file://0001-systemd-networkd.socket-Add-conflict-with-shutdown.t.patch \
    file://systemd-journal-flush-override.conf \
"

do_install_append() {
    if ${@bb.utils.contains('DISTRO_FEATURES', 'read-only-rootfs', 'true', 'false', d)}; then
        install -d ${D}${sysconfdir}/systemd/system/systemd-journal-flush.service.d
        install -m 0644 ${WORKDIR}/systemd-journal-flush-override.conf ${D}${sysconfdir}/systemd/system/systemd-journal-flush.service.d
    fi
}
