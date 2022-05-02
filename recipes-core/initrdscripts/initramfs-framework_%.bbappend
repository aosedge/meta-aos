FILESEXTRAPATHS_prepend := "${THISDIR}/initramfs-framework:"

SRC_URI += " \
    file://opendisk \
"

PACKAGES += " \
    initramfs-module-opendisk \
"

SUMMARY_initramfs-module-opendisk = "initramfs support for opening encrypted disk"
RDEPENDS_initramfs-module-opendisk = "${PN}-base diskencryption"
FILES_initramfs-module-opendisk = "/init.d/05-opendisk"

do_install_append() {
    # opendisk
    install -m 0755 ${WORKDIR}/opendisk ${D}/init.d/05-opendisk
}
