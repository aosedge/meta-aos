FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI += "file://openssl-aos.cnf"

PKCS11_PROVIDER_PATH ?= "${libdir}/ossl-modules/pkcs11.so"
LEGACY_PROVIDER_PATH ?= "${libdir}/ossl-modules/legacy.so"
HSM_MODULE_PATH ?= "${libdir}/softhsm/libsofthsm2.so"

do_install:append:class-target() {
    sed -e 's,@PKCS11_PROVIDER_PATH@,${PKCS11_PROVIDER_PATH},g' \
        -e 's,@LEGACY_PROVIDER_PATH@,${LEGACY_PROVIDER_PATH},g' \
        -e 's,@HSM_MODULE_PATH@,${HSM_MODULE_PATH},g' \
        ${WORKDIR}/openssl-aos.cnf > ${D}${sysconfdir}/ssl/openssl-aos.cnf

    echo ".include ${sysconfdir}/ssl/openssl-aos.cnf" >> ${D}${sysconfdir}/ssl/openssl.cnf
}

PREFERRED_VERSION_pkcs11-provider = "1.0"

RDEPENDS:${PN}:class-target += " \
    pkcs11-provider \
"
