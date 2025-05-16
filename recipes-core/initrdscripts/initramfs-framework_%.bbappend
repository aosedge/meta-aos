FILESEXTRAPATHS:prepend := "${THISDIR}/initramfs-framework:"

SRC_URI += " \
    file://aosupdate \
    file://kmsglog \
    file://machineid \
    file://opendisk \
    file://rundir \
    file://vardir \
"

PACKAGES += " \
    initramfs-module-aosupdate \
    initramfs-module-kmsglog \
    initramfs-module-machineid \
    initramfs-module-opendisk \
    initramfs-module-rundir \
    initramfs-module-vardir \
"

SUMMARY:initramfs-module-aosupdate = "initramfs support for Aos rootfs update"
RDEPENDS:initramfs-module-aosupdate = "${PN}-base rsync"
FILES:initramfs-module-aosupdate = "/init.d/95-aosupdate"
RRECOMMENDS:initramfs-module-aosupdate = " \
    kernel-module-loop \
    kernel-module-overlay \
    kernel-module-squashfs \
    ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ' \
        packagegroup-selinux-minimal \
        policycoreutils-hll \
        policycoreutils-loadpolicy \
    ', '', d)} \
"

SUMMARY:initramfs-module-kmsglog = "redirect log messages to kmsg"
RDEPENDS:initramfs-module-kmsglog = "${PN}-base"
FILES:initramfs-module-kmsglog = "/init.d/00-kmsglog"

SUMMARY:initramfs-module-machineid = "bind /etc/machine-id to /var/machine-id"
RDEPENDS:initramfs-module-machineid = "${PN}-base initramfs-module-vardir"
FILES:initramfs-module-machineid = "/init.d/96-machineid"

SUMMARY:initramfs-module-opendisk = "initramfs support for opening encrypted disk"
RDEPENDS:initramfs-module-opendisk = "${PN}-base diskencryption"
FILES:initramfs-module-opendisk = "/init.d/05-opendisk"

SUMMARY:initramfs-module-rundir = "initramfs support for sharing /run dir to local"
RDEPENDS:initramfs-module-rundir = "${PN}-base"
FILES:initramfs-module-rundir = "/init.d/00-rundir"

SUMMARY:initramfs-module-vardir = "mount RW /var directory"
RDEPENDS:initramfs-module-vardir = "${PN}-base"
FILES:initramfs-module-vardir = "/init.d/02-vardir"

do_install:append() {
    # aosupdate
    install -m 0755 ${WORKDIR}/aosupdate ${D}/init.d/95-aosupdate

    # kmsglog
    install -m 0755 ${WORKDIR}/kmsglog ${D}/init.d/00-kmsglog

    # machineid
    install -m 0755 ${WORKDIR}/machineid ${D}/init.d/96-machineid

    # opendisk
    install -m 0755 ${WORKDIR}/opendisk ${D}/init.d/05-opendisk

    # rundir
    install -m 0755 ${WORKDIR}/rundir ${D}/init.d/00-rundir

    # vardir
    install -m 0755 ${WORKDIR}/vardir ${D}/init.d/02-vardir
}
