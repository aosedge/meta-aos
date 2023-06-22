# This class generates partition image from WIC

AOS_PART_IMAGE_PARTNO ??= ""
AOS_PART_IMAGE_DIR ??= "${WORKDIR}/update"
AOS_PART_IMAGE_FILE ??= "${IMAGE_BASENAME}-${MACHINE}-p${AOS_PART_IMAGE_PARTNO}.gz"
AOS_PART_SOURCE_DIR ??= "${WORKDIR}/build-wic"

# Functions

do_create_part_image() {
    if [ -z ${AOS_PART_IMAGE_PARTNO} ] || [ ${AOS_PART_IMAGE_PARTNO} = "none" ]; then
        exit 0
    fi

    PART_FILE=$(find -L ${AOS_PART_SOURCE_DIR} -name "*direct.p${AOS_PART_IMAGE_PARTNO}")

    if [ -z ${PART_FILE} ]; then
        bbfatal "WIC partition not found"
    fi

    gzip -c ${PART_FILE} > ${AOS_PART_IMAGE_DIR}/${AOS_PART_IMAGE_FILE}
}
