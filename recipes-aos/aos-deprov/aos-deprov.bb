DESCRIPTION = "Aos unprovisioning script"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://deprovision.sh \
    file://clearhsm.sh \
"

S = "${WORKDIR}"

FILES:${PN} = " \
    ${aos_opt_dir} \
"

RDEPENDS:${PN} += "aos-setupdisk"

do_install() {
    install -d ${D}${aos_opt_dir}
    install -m 0755 ${S}/deprovision.sh ${D}${aos_opt_dir}
    install -m 0755 ${S}/clearhsm.sh ${D}${aos_opt_dir}
}
