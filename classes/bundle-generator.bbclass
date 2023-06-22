# This class containes functions to generate update bundle

AOS_BUNDLE_DIR ??= "${DEPLOY_DIR_IMAGE}/update"
AOS_BUNDLE_FILE ??= "${IMAGE_BASENAME}-${MACHINE}-${PV}.bundle.tar"
AOS_BUNDLE_WORK_DIR ??= "${WORKDIR}/update"

do_pack_bundle() {
    tar cf ${AOS_BUNDLE_DIR}/${AOS_BUNDLE_FILE} -C ${AOS_BUNDLE_WORK_DIR}/ .
}
