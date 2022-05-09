SUMMARY = "Target to generate AOS update bundle"
LICENSE = "Apache-2.0"

# Inherit
inherit metadata-generator bundle-generator rootfs-image-generator externalsrc

# Depends
DEPENDS_append = " ostree-native squashfs-tools-native"

# Variables

BOARD_MODEL ?= "spider;1.0"

# Bundle image version used as suffix in the bundle name and default version for
# other components
BUNDLE_IMAGE_VERSION ?= "2.1.0"
# Bundle previous version used as default reference version for incremenral
# updates
BUNDLE_PREVIOUS_VERSION ?= "2.0.0"

BUNDLE_DIR ?= "${DEPLOY_DIR}/update"
BUNDLE_FILE ?= "${IMAGE_BASENAME}-${MACHINE}-${BUNDLE_IMAGE_VERSION}.tar"

BUNDLE_DOM0_TYPE ?= "full"
BUNDLE_DOMD_TYPE ?= "full"
#BUNDLE_DOMF_TYPE ?= "full"

BUNDLE_OSTREE_REPO ?= "${DEPLOY_DIR}/update/repo"

# Dependencies

do_build[depends] += "core-image-thin-initramfs:do_${BB_DEFAULT_TASK}"
do_build[cleandirs] = "${BUNDLE_WORK_DIR}"
do_build[dirs] = "${BUNDLE_DIR}"
do_create_dom0_image[cleandirs] = "${WORKDIR}/rootfs"

# Configuration

BUNDLE_DOM0_ID = "dom0"
BUNDLE_DOMD_ID = "domd"
BUNDLE_DOMF_ID = "domf"

BUNDLE_DOM0_DESC = "Dom0 image"
BUNDLE_DOMD_DESC = "DomD image"
BUNDLE_DOMF_DESC = "DomF image"

ROOTFS_IMAGE_DIR = "${BUNDLE_WORK_DIR}"
ROOTFS_EXCLUDE_FILES = "var/*"

# Dom0 image version
DOM0_IMAGE_VERSION ?= "${BUNDLE_IMAGE_VERSION}"
# DomD image version
DOMD_IMAGE_VERSION ?= "${BUNDLE_IMAGE_VERSION}"
# DomF image version
DOMF_IMAGE_VERSION ?= "${BUNDLE_IMAGE_VERSION}"

# DomD reference version, used for incremental update.
DOMD_REF_VERSION ?= "${BUNDLE_PREVIOUS_VERSION}"
# DomF reference version, used for incremental update.
DOMF_REF_VERSION ?= "${BUNDLE_PREVIOUS_VERSION}"

DOM0_IMAGE_FILE = "${BUNDLE_DOM0_ID}-${MACHINE}-${BUNDLE_DOM0_TYPE}-${DOM0_IMAGE_VERSION}.gz"
DOMD_IMAGE_FILE = "${BUNDLE_DOMD_ID}-${XT_DOMD_MACHINE}-${BUNDLE_DOMD_TYPE}-${DOMD_IMAGE_VERSION}.squashfs"
DOMF_IMAGE_FILE = "${BUNDLE_DOMF_ID}-${XT_DOMD_MACHINE}-${BUNDLE_DOMF_TYPE}-${DOMF_IMAGE_VERSION}.squashfs"

DOMD_IMAGES_DIR = "${EXTERNALSRC_pn-domd}"
DOM0_PART_SIZE = "128"
DOM0_PART_LABEL = "boot"

#DOM0_ROOT = "${DEPLOY_DIR}/${MACHINE}"
# Tasks
do_compile() {
    install -d ${BUNDLE_WORK_DIR}
}

python do_create_metadata() {
    components_metadata = []
    
    if d.getVar("BUNDLE_DOM0_TYPE") == "full":
        components_metadata.append(create_component_metadata(d.getVar("BUNDLE_DOM0_ID"), d.getVar("DOM0_IMAGE_FILE"),
            d.getVar("DOM0_IMAGE_VERSION"), d.getVar("BUNDLE_DOM0_DESC")))
    elif d.getVar("BUNDLE_DOM0_TYPE"):
        bb.fatal("Wrong dom0 image type: %s" % d.getVar("BUNDLE_DOM0_TYPE"))

    if d.getVar("BUNDLE_DOMD_TYPE"):
        install_dep = {}
        annotations = {}

        if d.getVar("BUNDLE_DOMD_TYPE") == "incremental":
            install_dep = create_dep(d.getVar("BUNDLE_DOMD_ID"), d.getVar("DOMD_REF_VERSION"))
            annotations = {"type": "incremental"}
        elif d.getVar("BUNDLE_DOMD_TYPE") == "full":
            annotations = {"type": "full"}
        else:
            bb.fatal("Wrong domd image type: %s" % d.getVar("BUNDLE_DOMD_TYPE"))

        components_metadata.append(create_component_metadata(d.getVar("BUNDLE_DOMD_ID"), d.getVar("DOMD_IMAGE_FILE"),
            d.getVar("DOMD_IMAGE_VERSION"), d.getVar("BUNDLE_DOMD_DESC"), install_dep, None, annotations))

    if d.getVar("BUNDLE_DOMF_TYPE"):
        install_dep = {}
        annotations = {}

        if d.getVar("BUNDLE_DOMF_TYPE") == "incremental":
            install_dep = create_dep(d.getVar("BUNDLE_DOMF_ID"), d.getVar("DOMF_REF_VERSION"))
            annotations = {"type": "incremental"}
        elif d.getVar("BUNDLE_DOMF_TYPE") == "full":
            annotations = {"type": "full"}
        else:
            bb.fatal("Wrong domf image type: %s" % d.getVar("BUNDLE_DOMF_TYPE"))

        components_metadata.append(create_component_metadata(d.getVar("BUNDLE_DOMF_ID"), d.getVar("DOMF_IMAGE_FILE"),
            d.getVar("DOMF_IMAGE_VERSION"), d.getVar("BUNDLE_DOMF_DESC"), install_dep, None, annotations))

    write_image_metadata(d.getVar("BUNDLE_WORK_DIR"), d.getVar("BOARD_MODEL"), components_metadata)
}

do_create_dom0_image() {
    if [ -z ${BUNDLE_DOM0_TYPE} ] || [ ${BUNDLE_DOM0_TYPE} = "none" ]; then
        exit 0
    fi

    dom0_root="${DEPLOY_DIR}/images/${MACHINE}"

    image=`find $dom0_root -name Image`
    uinitramfs=`find $dom0_root -name uInitramfs`

    domd_root=${DOMD_IMAGES_DIR}
    name=`ls $domd_root`
    dom0dtb=`find $domd_root -name "${XT_DOMD_SOC_FAMILY}-${XT_DOMD_MACHINE}-xen.dtb"`
    xenpolicy=`find $domd_root -name xenpolicy-${XT_DOMD_MACHINE}`
    xenuimage=`find $domd_root -name xen-uImage`

    install -d ${WORKDIR}/rootfs/boot

    for f in $image $uinitramfs $dom0dtb $xenpolicy $xenuimage ; do
        cp -Lrf $f ${WORKDIR}/rootfs/boot
    done

    dd if=/dev/zero of=${WORKDIR}/dom0.part bs=1M count=${DOM0_PART_SIZE}
    mkfs.ext4 -F -L ${DOM0_PART_LABEL} -E root_owner=0:0 -d ${WORKDIR}/rootfs ${WORKDIR}/dom0.part

    gzip < ${WORKDIR}/dom0.part > ${BUNDLE_WORK_DIR}/${DOM0_IMAGE_FILE}
}

prepare_rootfs() {
    [ -e ${WORKDIR}/domx_rootfs ] && rm -rf ${WORKDIR}/domx_rootfs
    install -d ${WORKDIR}/domx_rootfs
    tar -C ${WORKDIR}/domx_rootfs -xjf ${ROOTFS_SOURCE_TAR}
}

python do_create_domd_image() {
    d.setVar("ROOTFS_OSTREE_REPO", os.path.join(d.getVar("BUNDLE_OSTREE_REPO"), d.getVar("BUNDLE_DOMD_ID")))
    d.setVar("ROOTFS_IMAGE_TYPE", d.getVar("BUNDLE_DOMD_TYPE"))
    d.setVar("ROOTFS_IMAGE_VERSION", d.getVar("DOMD_IMAGE_VERSION"))
    d.setVar("ROOTFS_REF_VERSION", d.getVar("DOMD_REF_VERSION"))
    d.setVar("ROOTFS_IMAGE_FILE", d.getVar("DOMD_IMAGE_FILE"))
    d.setVar("ROOTFS_SOURCE_DIR", os.path.join(d.getVar("WORKDIR"),"domx_rootfs"))
    d.setVar("ROOTFS_SOURCE_TAR", os.path.join(d.getVar("DOMD_IMAGES_DIR"), "{}-{}.tar.bz2".format("rcar-image-minimal", d.getVar("XT_DOMD_MACHINE"))))

    bb.build.exec_func("prepare_rootfs", d)
    bb.build.exec_func("do_create_rootfs_image", d)
}

python do_create_domf_image() {
    if d.getVar("BUNDLE_DOMF_TYPE"):
        d.setVar("ROOTFS_OSTREE_REPO", os.path.join(d.getVar("BUNDLE_OSTREE_REPO"), d.getVar("BUNDLE_DOMF_ID")))
        d.setVar("ROOTFS_IMAGE_TYPE", d.getVar("BUNDLE_DOMF_TYPE"))
        d.setVar("ROOTFS_IMAGE_VERSION", d.getVar("DOMF_IMAGE_VERSION"))
        d.setVar("ROOTFS_REF_VERSION", d.getVar("DOMF_REF_VERSION"))
        d.setVar("ROOTFS_IMAGE_FILE", d.getVar("DOMF_IMAGE_FILE"))
        d.setVar("ROOTFS_SOURCE_DIR", os.path.join(d.getVar("WORKDIR"),"domx_rootfs"))
        d.setVar("ROOTFS_SOURCE_TAR", os.path.join(d.getVar("DOMF_IMAGES_DIR"), "{}-{}.tar.bz2".format("rcar-image-minimal", d.getVar("XT_DOMD_MACHINE"))))

        bb.build.exec_func("prepare_rootfs", d)
        bb.build.exec_func("do_create_rootfs_image", d)
}

python do_create_bundle() {
    if not d.getVar("BUNDLE_DOM0_TYPE") and not d.getVar("BUNDLE_DOMD_TYPE") and not d.getVar("BUNDLE_DOMF_TYPE"):
        bb.fatal("There are no componenets to add to the bundle")

    bb.build.exec_func("do_create_metadata", d)
    bb.build.exec_func("do_create_dom0_image", d)
    bb.build.exec_func("do_create_domd_image", d)
    bb.build.exec_func("do_create_domf_image", d)
    bb.build.exec_func("do_pack_bundle", d)
}

addtask create_bundle after do_compile before do_build
