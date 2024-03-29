FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI += "file://openssl-engine.conf"

HSM_MODULE_PATH ?= "${libdir}/softhsm/libsofthsm2.so"

do_install:append:class-target() {
    if ! grep -q "^\[engine_section\]" ${D}${sysconfdir}/ssl/openssl.cnf; then
        sed -e 's,@PKCS11_ENGINE_PATH@,${libdir}/engines-3/pkcs11.so,g' \
            -e 's,@HSM_MODULE_PATH@,${HSM_MODULE_PATH},g' \
            ${WORKDIR}/openssl-engine.conf >> ${D}${sysconfdir}/ssl/openssl.cnf
    fi
}

RDEPENDS:${PN}:class-target += " \
    libp11 \
"
