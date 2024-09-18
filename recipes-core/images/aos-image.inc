DESCRIPTION = "Aos base image"

SUMMARY = "An image which contains AOS components"
LICENSE = "Apache-2.0"

inherit ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', 'selinux-image', '', d)}

DEPENDS += "e2fsprogs-native"

# Enable RO rootfs
IMAGE_FEATURES:append = " read-only-rootfs"

# Set rootfs version

do_rootfs[vardeps] += "AOS_ROOTFS_IMAGE_VERSION AOS_BOOT_IMAGE_VERSION"

ROOTFS_POSTPROCESS_COMMAND:append = "set_rootfs_version; create_boot_version;"

set_rootfs_version() {
    if [ -z "$AOS_ROOTFS_IMAGE_VERSION" ]; then
        install -d ${IMAGE_ROOTFS}/etc/aos

        echo "VERSION=\"${AOS_ROOTFS_IMAGE_VERSION}\"" > ${IMAGE_ROOTFS}/etc/aos/version
    fi
}

create_boot_version() {
    if [ -z "$AOS_BOOT_IMAGE_VERSION" ]; then
        install -d ${DEPLOY_DIR_IMAGE}/aos/boot

        echo "VERSION=\"${AOS_BOOT_IMAGE_VERSION}\"" > ${DEPLOY_DIR_IMAGE}/aos/boot/version
    fi
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

AOS_SHARED_RESOURCE_DIR = "${TMPDIR}/work-shared/${PN}-${MACHINE}"

do_create_shared_links[cleandirs] = "${AOS_SHARED_RESOURCE_DIR}"

# We need to have shared resources in work-shared dir for the layer functionality.
do_create_shared_links() {
    if [ -d ${IMAGE_ROOTFS} ]; then
        ln -r -s ${IMAGE_ROOTFS} ${AOS_SHARED_RESOURCE_DIR}/rootfs
    fi
}

addtask create_shared_links after do_image_qa do_image_wic before do_image_complete

# Create RW partitions

AOS_VAR_PART_SIZE ?= "524288"
AOS_HOME_PART_SIZE ?= ""

mk_dir_fs() {
    local dir="$1"
    local size="$2"
    local out_file="${DEPLOY_DIR_IMAGE}/${IMAGE_BASENAME}-${MACHINE}-${dir}.ext4"

    dd if=/dev/zero of=${out_file} count=${size} bs=1024
    mkfs.ext4 ${out_file} -d ${IMAGE_ROOTFS}/${dir}
    fsck.ext4 -pvfD ${out_file} || [ $? -le 3 ]
}

fakeroot do_create_rw_parts() {
    if [ ! -z "${AOS_VAR_PART_SIZE}" ]; then
        mk_dir_fs "var" "${AOS_VAR_PART_SIZE}"
    fi

    if [ ! -z "${AOS_HOME_PART_SIZE}" ]; then
        mk_dir_fs "home" "${AOS_HOME_PART_SIZE}"
    fi
}

addtask create_rw_parts after do_image_qa do_image_wic before do_image_complete

# Packages

IMAGE_INSTALL:append = " \
    aos-iamanager \
    aos-servicemanager \
    aos-updatemanager \
    aos-deprov \
    ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ' \
        packagegroup-selinux-minimal \
        packagegroup-selinux-policycoreutils \
        selinux-autorelabel \
        ', '', d)} \
"

IMAGE_INSTALL:append:aos-main-node = " \
    aos-communicationmanager \
    aos-provfirewall \
    aos-vis \
"

TOOLCHAIN_HOST_TASK:append = " \
    nativesdk-protobuf \
    nativesdk-protobuf-dev \
    nativesdk-grpc \
    nativesdk-grpc-dev \
    nativesdk-grpc-compiler \
"

TOOLCHAIN_TARGET_TASK:append = " protobuf-staticdev"
