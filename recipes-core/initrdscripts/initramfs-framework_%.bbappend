FILESEXTRAPATHS_prepend := "${THISDIR}/initramfs-framework:"

SRC_URI += " \
    file://opendisk \
    file://rundir \
"

PACKAGES += " \
    initramfs-module-opendisk \
    initramfs-module-rundir \
"

SUMMARY_initramfs-module-opendisk = "initramfs support for opening encrypted disk"
RDEPENDS_initramfs-module-opendisk = "${PN}-base diskencryption"
FILES_initramfs-module-opendisk = "/init.d/05-opendisk"

SUMMARY_initramfs-module-rundir = "initramfs support for sharing /run dir to local"
RDEPENDS_initramfs-module-rundir = "${PN}-base"
FILES_initramfs-module-rundir = "/init.d/00-rundir"

do_install_append() {
    # opendisk
    install -m 0755 ${WORKDIR}/opendisk ${D}/init.d/05-opendisk

    # rundir
    install -m 0755 ${WORKDIR}/rundir ${D}/init.d/00-rundir
}
