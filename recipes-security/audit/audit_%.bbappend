FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " file://audit-rules-append.conf"

do_install:append() {
    # Append custom audit rules to the end of audit.rules
    cat ${WORKDIR}/audit-rules-append.conf >> ${D}${sysconfdir}/audit/audit.rules
}
