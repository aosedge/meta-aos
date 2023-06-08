FILESEXTRAPATHS:prepend := "${THISDIR}/initramfs-framework:"

SRC_URI += " \
    file://aosupdate \
    file://machineid \
    file://opendisk \
    file://rundir \
    file://selinux \
    file://vardir \
"

PACKAGES += " \
    initramfs-module-aosupdate \
    initramfs-module-machineid \
    initramfs-module-opendisk \
    initramfs-module-rundir \
    ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', 'initramfs-module-selinux', '', d)} \
    initramfs-module-vardir \
"

SUMMARY:initramfs-module-aosupdate = "initramfs support for Aos rootfs update"
RDEPENDS:initramfs-module-aosupdate = "${PN}-base rsync"
FILES:initramfs-module-aosupdate = "/init.d/95-aosupdate"
RRECOMMENDS:initramfs-module-aosupdate = " \
    kernel-module-loop \
    kernel-module-overlay \
    kernel-module-squashfs \
"

SUMMARY:initramfs-module-machineid = "bind /etc/machine-id to /var/machine-id"
RDEPENDS:initramfs-module-machineid = "${PN}-base initramfs-module-vardir"
FILES:initramfs-module-machineid = "/init.d/96-machineid"

SUMMARY:initramfs-module-opendisk = "initramfs support for opening encrypted disk"
RDEPENDS:initramfs-module-opendisk = "${PN}-base diskencryption"
FILES:initramfs-module-opendisk = "/init.d/05-opendisk"

SUMMARY:initramfs-module-rundir = "initramfs support for sharing /run dir to local"
RDEPENDS:initramfs-module-rundir = "${PN}-base"
FILES:initramfs-module-rundir = "/init.d/00-rundir"

SUMMARY:initramfs-module-selinux = "initramfs support for selinux"
RDEPENDS:initramfs-module-selinux = " \
    ${PN}-base \
    packagegroup-selinux-minimal \
    policycoreutils-hll \
    policycoreutils-loadpolicy \
"
FILES:initramfs-module-selinux = "/init.d/03-selinux"

SUMMARY:initramfs-module-vardir = "mount RW /var directory"
RDEPENDS:initramfs-module-vardir = "${PN}-base"
FILES:initramfs-module-vardir = "/init.d/02-vardir"

do_install:append() {
    # aosupdate
    install -m 0755 ${WORKDIR}/aosupdate ${D}/init.d/95-aosupdate

    # machineid
    install -m 0755 ${WORKDIR}/machineid ${D}/init.d/96-machineid

    # opendisk
    install -m 0755 ${WORKDIR}/opendisk ${D}/init.d/05-opendisk

    # rundir
    install -m 0755 ${WORKDIR}/rundir ${D}/init.d/00-rundir

    # selinux
    if ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', 'true', 'false', d)}; then
        install -m 0755 ${WORKDIR}/selinux ${D}/init.d/03-selinux
    fi

    # vardir
    install -m 0755 ${WORKDIR}/vardir ${D}/init.d/02-vardir
}
