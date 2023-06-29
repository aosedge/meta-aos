DESCRIPTION = "Aos base image"

SUMMARY = "An image which contains AOS components"
LICENSE = "Apache-2.0"

inherit ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', 'selinux-image', '', d)}

# Enable RO rootfs
IMAGE_FEATURES:append = " read-only-rootfs"

# Set rootfs version

ROOTFS_POSTPROCESS_COMMAND:append = "set_rootfs_version;"

set_rootfs_version() {
    install -d ${IMAGE_ROOTFS}/etc/aos

    echo "VERSION=\"${AOS_ROOTFS_IMAGE_VERSION}\"" > ${IMAGE_ROOTFS}/etc/aos/version
}

# Set unit model

AOS_UNIT_MODEL ?= "aos-unit"
AOS_UNIT_VERSION ?= "1.0"

ROOTFS_POSTPROCESS_COMMAND:append:aos-main-node = "set_unit_model;"

set_unit_model() {
    install -d ${IMAGE_ROOTFS}/etc/aos

    echo "${AOS_UNIT_MODEL};${AOS_UNIT_VERSION}" > ${IMAGE_ROOTFS}/etc/aos/unit_model
}

# Shared links

AOS_SHARED_RESOURCE_DIR = "${TMPDIR}/work-shared/${IMAGE_BASENAME}-${MACHINE}"

do_create_shared_links[cleandirs] = "${AOS_SHARED_RESOURCE_DIR}"

AOS_BUILD_WIC_DIR = "${WORKDIR}/build-wic"

# We need to have shared resources in work-shared dir for the layer functionality.
# Creating symlink IMAGE_ROOTFS and BUILD_WIC_DIR to work-shared to get an access to them by
# layers and update
do_create_shared_links() {
    if [ -d ${IMAGE_ROOTFS} ]; then
        ln -r -s ${IMAGE_ROOTFS} ${AOS_SHARED_RESOURCE_DIR}/rootfs
    fi

    if [ -d ${AOS_BUILD_WIC_DIR} ]; then
        ln -r -s ${AOS_BUILD_WIC_DIR} ${AOS_SHARED_RESOURCE_DIR}/build-wic
    fi
}

addtask create_shared_links after do_image_qa do_image_wic before do_image_complete

# Packages

IMAGE_INSTALL:append = " \
    aos-iamanager \
    aos-servicemanager \
    aos-updatemanager \
    ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ' \
        packagegroup-selinux-minimal \
        packagegroup-selinux-policycoreutils \
        aos-selinux-autorelabel \
        ', '', d)} \
"

IMAGE_INSTALL:append:aos-main-node = " \
    aos-communicationmanager \
    aos-provfirewall \
    aos-vis \
"
