DESCRIPTION = "Aos provisioning finish script"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://provfinish.sh \
"

S = "${WORKDIR}"

FILES:${PN} = " \
    ${aos_var_dir} \
    ${aos_opt_dir} \
"

RDEPENDS:${PN} = "aos-target"

do_install() {
    install -d ${D}${aos_var_dir}

    install -d ${D}${aos_opt_dir}
    install -m 0755 ${S}/provfinish.sh ${D}${aos_opt_dir}
}
