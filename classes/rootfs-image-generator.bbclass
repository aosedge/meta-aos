# This class generates squashfs images for rootfs based on ostree

# Configuration

ROOTFS_IMAGE_TYPE ??= ""
ROOTFS_IMAGE_VERSION ??= "${PV}"
ROOTFS_REF_VERSION ??= "${PV}"
ROOTFS_IMAGE_DIR ??= "${WORKDIR}/update"
ROOTFS_IMAGE_FILE ??= "${IMAGE_BASENAME}-${MACHINE}-${ROOTFS_IMAGE_VERSION}.rootfs.squashfs"
ROOTFS_OSTREE_REPO ??= "${DEPLOY_DIR_IMAGE}/update/repo"
ROOTFS_EXCLUDE_FILES ??= "var/* home/*"
ROOTFS_SOURCE_DIR ??= "${IMAGE_ROOTFS}"

# Variables

BUILD_WIC_DIR="${WORKDIR}/build-wic"
ROOTFS_DIFF_DIR = "${WORKDIR}/rootfs_diff"
OSTREE_REPO_TYPE = "archive"

# Dependencies

DEPENDS_append = " \
    ostree-native \
    squashfs-tools-native \
    ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', 'policycoreutils-native', '', d)} \
"

# Functions

init_ostree_repo() {
    bbnote "Ostree repo doesn't exist. Create ostree repo"

    mkdir -p ${ROOTFS_OSTREE_REPO}
    ostree --repo=${ROOTFS_OSTREE_REPO} init --mode=${OSTREE_REPO_TYPE}
}

ostree_commit() {
    ostree --repo=${ROOTFS_OSTREE_REPO} commit \
           --tree=dir=${ROOTFS_SOURCE_DIR}/ \
           --skip-if-unchanged \
           --branch=${ROOTFS_IMAGE_VERSION} \
           --subject="${ROOTFS_IMAGE_VERSION}-${DATATIME}"
}

create_full_update() {
    mksquashfs ${ROOTFS_SOURCE_DIR}/ ${ROOTFS_IMAGE_DIR}/${ROOTFS_IMAGE_FILE} \
        -noappend -wildcards -all-root -e ${ROOTFS_EXCLUDE_FILES}
}

create_incremental_update() {
    rm -rf ${ROOTFS_DIFF_DIR}
    mkdir -p ${ROOTFS_DIFF_DIR}

    ostree --repo=${ROOTFS_OSTREE_REPO} diff ${ROOTFS_REF_VERSION} ${ROOTFS_IMAGE_VERSION} |
    while read -r item; do
        action=${item%% *}
        item=${item##* }

        if [ ${action} = "A" ] || [ ${action} = "M" ]; then
            if [ -d ${ROOTFS_SOURCE_DIR}${item} ]; then
                mkdir -p ${ROOTFS_DIFF_DIR}${item}
            else
                mkdir -p $(dirname ${ROOTFS_DIFF_DIR}${item})
                cp -a ${ROOTFS_SOURCE_DIR}${item} ${ROOTFS_DIFF_DIR}${item}
            fi
        elif [ ${action} = "D" ]; then
            mkdir -p $(dirname ${ROOTFS_DIFF_DIR}${item})
            mknod ${ROOTFS_DIFF_DIR}${item} c 0 0 
        fi
    done

    if [ ! "$(ls -A ${ROOTFS_DIFF_DIR})" ]; then
        bbfatal "incremental roofs update is empty"
    fi

    mksquashfs ${ROOTFS_DIFF_DIR} ${ROOTFS_IMAGE_DIR}/${ROOTFS_IMAGE_FILE} \
        -noappend -wildcards -all-root -e ${ROOTFS_EXCLUDE_FILES}
}

do_create_rootfs_image() {
    if [ -z ${ROOTFS_IMAGE_TYPE} ] || [ ${ROOTFS_IMAGE_TYPE} = "none" ]; then
        exit 0
    fi

    if [ ! -d ${ROOTFS_OSTREE_REPO}/refs ]; then
        init_ostree_repo
    fi

    if ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', 'true', 'false', d)}; then
        ROOTFS_FULL_PATH=$(realpath ${ROOTFS_SOURCE_DIR})
        setfiles -m -r ${ROOTFS_FULL_PATH} ${ROOTFS_FULL_PATH}/etc/selinux/aos/contexts/files/file_contexts ${ROOTFS_FULL_PATH}
    fi

    ostree_commit

    if [ ${ROOTFS_IMAGE_TYPE} = "full" ]; then
        bbnote "Create full rootfs image"
        create_full_update
    elif [ "${ROOTFS_IMAGE_TYPE}" = "incremental" ]; then
        bbnote "Create incremental rootfs image"
        create_incremental_update
    else
        bbfatal "unknown rootfs image type: ${ROOTFS_IMAGE_TYPE}"
    fi
}
