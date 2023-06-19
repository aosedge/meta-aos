DESCRIPTION = "Aos provisioning finish script"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://setupdisk.sh \
    file://aosdisk_main.cfg \
    file://aosdisk_secondary.cfg \
"

S = "${WORKDIR}"

FILES:${PN} = " \
    ${aos_opt_dir} \
"

RDEPENDS:${PN} = " \
    bash \
    diskencryption \
    lvm2 \
    lvm2-udevrules \
    e2fsprogs \
    quota \
"

AOS_DISK_CONFIG:aos-main-node = "aosdisk_main.cfg"
AOS_DISK_CONFIG:aos-secondary-node = "aosdisk_secondary.cfg"

do_install() {
    install -d ${D}${aos_opt_dir}
    install -m 0755 ${S}/setupdisk.sh ${D}${aos_opt_dir}
    install -m 0644 ${S}/${AOS_DISK_CONFIG} ${D}${aos_opt_dir}/aosdisk.cfg
}
