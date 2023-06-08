DESCRIPTION = "Disk encryption utility"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://diskencryption.sh \
"

S = "${WORKDIR}"

RDEPENDS:${PN} = " \
    cryptsetup \
    lvm2-udevrules \
    opensc \
    openssl-bin \
    coreutils \
    jq \
"

RRECOMMENDS:${PN} += " \
    kernel-module-dm-mod \
"

FILES:${PN} = " \
    ${bindir}/diskencryption.sh \
"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${S}/diskencryption.sh ${D}${bindir}
}
