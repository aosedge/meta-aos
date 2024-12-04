# This class generates squashfs images for rootfs based on ostree

# Configuration

AOS_ROOTFS_IMAGE_TYPE ??= "full"
AOS_ROOTFS_IMAGE_VERSION ??= "${PV}"
AOS_ROOTFS_REF_VERSION ??= "${PV}"
AOS_ROOTFS_IMAGE_FILE ??= "${DEPLOY_DIR_IMAGE}/update/${IMAGE_BASENAME}-${MACHINE}-${ROOTFS_IMAGE_VERSION}.rootfs.squashfs"
AOS_ROOTFS_OSTREE_REPO ??= "${DEPLOY_DIR_IMAGE}/update/repo"
AOS_ROOTFS_EXCLUDE_ITEMS ??= ""
AOS_ROOTFS_SOURCE_DIR ??= "${TMPDIR}/work-shared/${IMAGE_BASENAME}-${MACHINE}/rootfs"

# Variables

ROOTFS_DIFF_DIR = "${WORKDIR}/rootfs_diff"
OSTREE_REPO_TYPE = "archive"

# Dependencies

DEPENDS:append = " \
    ostree-native \
    squashfs-tools-native \
    ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', 'policycoreutils-native', '', d)} \
"

# Functions

init_ostree_repo() {
    bbnote "Ostree repo doesn't exist. Create ostree repo"

    mkdir -p ${AOS_ROOTFS_OSTREE_REPO}
    ostree --repo=${AOS_ROOTFS_OSTREE_REPO} init --mode=${OSTREE_REPO_TYPE}
}

ostree_commit() {
    ostree --repo=${AOS_ROOTFS_OSTREE_REPO} commit \
           --tree=dir=${AOS_ROOTFS_SOURCE_DIR}/ \
           --skip-if-unchanged \
           --branch=${AOS_ROOTFS_IMAGE_VERSION} \
           --subject="${AOS_ROOTFS_IMAGE_VERSION}-${DATATIME}"
}

create_full_update() {
    mksquashfs ${AOS_ROOTFS_SOURCE_DIR}/ ${AOS_ROOTFS_IMAGE_FILE} \
        -noappend -wildcards -all-root \
        ${@'' if not d.getVar('AOS_ROOTFS_EXCLUDE_ITEMS') else '-e '+ d.getVar('AOS_ROOTFS_EXCLUDE_ITEMS')}
}

create_incremental_update() {
    rm -rf ${ROOTFS_DIFF_DIR}
    mkdir -p ${ROOTFS_DIFF_DIR}

    ostree --repo=${AOS_ROOTFS_OSTREE_REPO} diff ${AOS_ROOTFS_REF_VERSION} ${AOS_ROOTFS_IMAGE_VERSION} |
    while read -r item; do
        action="${item%% *}"
        item="${item#* }"
        item="${item#"${item%%[! ]*}"}"

        bbnote "${action} ${item}"

        src="${AOS_ROOTFS_SOURCE_DIR}${item}"
        dst="${ROOTFS_DIFF_DIR}${item}"

        if [ ${action} = "A" ] || [ ${action} = "M" ]; then
            if [ -L "${src}" ] && [ -d "${src}" ]; then
                cp -a "${src}" "${dst}"
            elif [ -d "${src}" ]; then
                mkdir -p "${dst}"
            else
                mkdir -p "$(dirname ${dst})"
                cp -a "${src}" "${dst}"
            fi
        elif [ ${action} = "D" ]; then
            mkdir -p "$(dirname ${dst})"
            mknod "${dst}" c 0 0 
        fi
    done

    if [ ! "$(ls -A ${ROOTFS_DIFF_DIR})" ]; then
        bbfatal "incremental roofs update is empty"
    fi

    if ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', 'true', 'false', d)}; then
        set_selinux_context "${ROOTFS_DIFF_DIR}" "${AOS_ROOTFS_SOURCE_DIR}"
    fi

    mksquashfs ${ROOTFS_DIFF_DIR} ${AOS_ROOTFS_IMAGE_FILE} \
        -noappend -wildcards -all-root \
        ${@'' if not d.getVar('AOS_ROOTFS_EXCLUDE_ITEMS') else '-e '+ d.getVar('AOS_ROOTFS_EXCLUDE_ITEMS')}
}

set_selinux_context() {
    target_dir="$1"
    rootfs_dir="$2"

    target_dir_full_path=$(realpath "$target_dir")
    rootfs_full_path=$(realpath "$rootfs_dir")

    setfiles -m -r "${target_dir_full_path}" \
    "${rootfs_full_path}/etc/selinux/aos/contexts/files/file_contexts" "${target_dir_full_path}"
}

fakeroot do_create_rootfs_image() {
    if [ ! -d ${AOS_ROOTFS_OSTREE_REPO}/refs ]; then
        init_ostree_repo
    fi

    if ${@bb.utils.contains('DISTRO_FEATURES', 'selinux', 'true', 'false', d)}; then
        set_selinux_context "${AOS_ROOTFS_SOURCE_DIR}" "${AOS_ROOTFS_SOURCE_DIR}"
    fi

    ostree_commit

    if [ ${AOS_ROOTFS_IMAGE_TYPE} = "full" ]; then
        bbnote "Create full rootfs image"
        create_full_update
    elif [ "${AOS_ROOTFS_IMAGE_TYPE}" = "incremental" ]; then
        bbnote "Create incremental rootfs image"
        create_incremental_update
    else
        bbfatal "unknown rootfs image type: ${AOS_ROOTFS_IMAGE_TYPE}"
    fi
}
