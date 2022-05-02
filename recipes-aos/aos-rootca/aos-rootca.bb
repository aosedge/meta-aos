DESCRIPTION = "Aos root certificate"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://Aos_Root_CA.pem \
"

S = "${WORKDIR}"

FILES_${PN} = " \
    ${sysconfdir} \
"

do_install() {
    install -d ${D}${sysconfdir}/ssl/certs
    install -m 0644 ${S}/Aos_Root_CA.pem ${D}${sysconfdir}/ssl/certs/
}
