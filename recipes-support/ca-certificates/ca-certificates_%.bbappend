FILESEXTRAPATHS:prepend := "${THISDIR}/ca-certificates:"

SRC_URI += " \
    file://AosRootCA.crt \
"

do_install:prepend() {
    install -d ${D}${datadir}/ca-certificates/aos
    install -m 0644 ${WORKDIR}/AosRootCA.crt ${D}${datadir}/ca-certificates/aos
}
