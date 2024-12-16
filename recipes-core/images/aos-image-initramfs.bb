DESCRIPTION = "Aos initramfs"

LICENSE = "Apache-2.0"

AOS_INITRAMFS_SCRIPTS ?= " \
    initramfs-module-aosupdate \
    initramfs-module-machineid \
    initramfs-module-udev \
    initramfs-module-vardir \
"

RRECOMMENDS:${PN} = " \
    kernel-module-overlay \
    kernel-module-squashfs \
"

# Don't allow the initramfs to contain a kernel
PACKAGE_EXCLUDE = "kernel-image-*"

PACKAGE_INSTALL = "${AOS_INITRAMFS_SCRIPTS} ${VIRTUAL-RUNTIME_base-utils} udev"

# Do not pollute the initrd image with rootfs features
IMAGE_FEATURES = ""

export IMAGE_BASENAME = "aos-image-initramfs"
IMAGE_LINGUAS = ""

IMAGE_FSTYPES = "${INITRAMFS_FSTYPES}"
inherit core-image

IMAGE_ROOTFS_SIZE = "8192"
IMAGE_ROOTFS_EXTRA_SPACE = "0"

COMPATIBLE_HOST = '(x86_64.*|i.86.*|arm.*|aarch64.*)-(linux.*)'
