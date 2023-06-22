# This class containes functions to generate layers

# Configuration

AOS_BASE_IMAGE ??= "aos-image"
AOS_PARENT_LAYER ??= "${AOS_BASE_IMAGE}"
AOS_LAYER_VERSION ??= "1"
AOS_LAYER_DIGEST_TYPE ??= "sha256"
AOS_LAYER_DEPLOY_DIR ??= "${DEPLOY_DIR_IMAGE}/layers"

# Inherit

inherit metadata-generator

# Dependencies

DEPENDS:append = " rsync-native"

# Variables

LAYER_MEDIA_TYPE = "application/vnd.aos.image.layer.v1.tar"
LAYER_WORK_DIR = "${WORKDIR}/layer"
PARENT_LAYER_ROOTFS = "${TMPDIR}/work-shared/${AOS_PARENT_LAYER}-${MACHINE}/rootfs"
ROOTFS_DIFF_DIR = "${WORKDIR}/rootfs_diff"
SHARED_DIGEST_DIR = "${TMPDIR}/work-shared/layers-${AOS_LAYER_DIGEST_TYPE}"

IMAGE_INSTALL:append = "${AOS_LAYER_FEATURES}"

# Dirs

do_create_layer[cleandirs] += "${LAYER_WORK_DIR} ${ROOTFS_DIFF_DIR}"
do_create_layer[depends] += "${AOS_PARENT_LAYER}:do_create_shared_links"
do_create_layer[dirs] += "${SHARED_DIGEST_DIR} ${AOS_LAYER_DEPLOY_DIR} ${LAYER_WORK_DIR}"

# Disable unneeded tasks

do_image[noexec] = "1"
do_image_wic[noexec] = "1"
do_image_complete[noexec] = "1"

# Tasks

do_create_rootfs_archive() {
    rsync -HAXlrvcm --append --progress --delete --compare-dest=${PARENT_LAYER_ROOTFS}/ ${IMAGE_ROOTFS}/* ${ROOTFS_DIFF_DIR}
    find ${ROOTFS_DIFF_DIR} -type d -empty -delete

    # Create layer rootfs tar

    IMAGE_ROOTFS_TAR=${LAYER_WORK_DIR}/${PN}.tar

    ${IMAGE_CMD_TAR} --numeric-owner -cf ${IMAGE_ROOTFS_TAR} -C ${ROOTFS_DIFF_DIR} .

    # Create layer rootfs digest

    DIGEST="$(${AOS_LAYER_DIGEST_TYPE}sum -b ${IMAGE_ROOTFS_TAR} | cut -d' ' -f1)"
    echo "${DIGEST} ${AOS_LAYER_VERSION}" >  ${SHARED_DIGEST_DIR}/${PN}.${AOS_LAYER_DIGEST_TYPE}

    mv ${IMAGE_ROOTFS_TAR} ${LAYER_WORK_DIR}/${DIGEST}
}

python do_create_whiteouts() {
    import os

    whiteoutPrefix = ".wh."
    whiteoutOpaqueDir = ".wh..wh..opq"

    whiteouts = d.getVar("AOS_LAYER_WHITEOUTS")
    if whiteouts is None:
        return

    for whiteout in list(whiteouts.split()):
        base = os.path.basename(whiteout)
        if base == "*":
            base = whiteoutOpaqueDir
        else:
            base = whiteoutPrefix + base

        whiteout_dir = d.getVar("IMAGE_ROOTFS") + os.path.dirname(whiteout)
        if not os.path.exists(whiteout_dir):
            os.makedirs(whiteout_dir)

        whiteout_file = os.path.join(whiteout_dir, base)

        if not os.path.exists(whiteout_file):
            open(whiteout_file, mode='x').close()
            os.chown(whiteout_file, 0, 0)

}

python do_create_metadata() {
    import os
    
    # Plarform info

    platform_info = create_layer_platform_info(d.getVar("MACHINE_ARCH"), d.getVar("TARGET_OS"), d.getVar("DISTRO_VERSION"),
        d.getVar("AOS_LAYER_FEATURES").split())

    # Annotations

    parent_id = ""
    parent_digest = ""

    if d.getVar("AOS_PARENT_LAYER") != d.getVar("AOS_BASE_IMAGE"):
        f = open(os.path.join(d.getVar("SHARED_DIGEST_DIR"),
            "{}.{}".format(d.getVar("AOS_PARENT_LAYER"), d.getVar("AOS_LAYER_DIGEST_TYPE"))), "r")
        
        data = f.read().split()
        parent_id = "{}:{}".format(d.getVar("AOS_PARENT_LAYER"), data[1])
        parent_digest = "{}:{}".format(d.getVar("AOS_LAYER_DIGEST_TYPE"), data[0])

    annotations = create_layer_annotations("{}:{}".format(d.getVar("PN"), d.getVar("AOS_LAYER_VERSION")), parent_id, parent_digest)

    # Write metadata

    f = open(os.path.join(d.getVar("SHARED_DIGEST_DIR"),
        "{}.{}".format(d.getVar("PN"), d.getVar("AOS_LAYER_DIGEST_TYPE"))), "r")

    data = f.read().split()
    digest = "{}:{}".format(d.getVar("AOS_LAYER_DIGEST_TYPE"), data[0])

    write_layer_metadata(d.getVar("LAYER_WORK_DIR"), d.getVar("LAYER_MEDIA_TYPE"), digest,
        os.path.getsize(os.path.join(d.getVar("LAYER_WORK_DIR"), data[0])), platform_info, annotations)
}

do_pack_layer() {
    ${IMAGE_CMD_TAR} --numeric-owner -czf ${AOS_LAYER_DEPLOY_DIR}/${PN}-${MACHINE}-${AOS_LAYER_VERSION}.tar.gz -C ${LAYER_WORK_DIR} .
}

fakeroot python do_create_layer() {
    bb.build.exec_func("do_create_whiteouts", d)
    bb.build.exec_func("do_create_rootfs_archive", d)
    bb.build.exec_func("do_create_metadata", d)
    bb.build.exec_func("do_pack_layer", d)
}

addtask do_create_layer after do_rootfs before do_image_qa
