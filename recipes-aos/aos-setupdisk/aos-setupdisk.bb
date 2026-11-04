DESCRIPTION = "Aos provisioning finish script"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://setupdisk.sh \
    file://aosdisk_main.cfg.in \
    file://aosdisk_secondary.cfg.in \
"

S = "${WORKDIR}"

FILES:${PN} = " \
    ${aos_opt_dir} \
"

RDEPENDS:${PN} = " \
    bash \
    cryptsetup \
    diskencryption \
    lvm2 \
    lvm2-udevrules \
    e2fsprogs \
    e2fsprogs-tune2fs \
    libdevmapper \
    quota \
"

RRECOMMENDS:${PN} += " \
    kernel-module-dm-integrity \
"

AOS_DISK_CONFIG:aos-main-node = "aosdisk_main.cfg.in"
AOS_DISK_CONFIG:aos-secondary-node = "aosdisk_secondary.cfg.in"

do_install() {
    install -d ${D}${aos_opt_dir}
    install -m 0755 ${S}/setupdisk.sh ${D}${aos_opt_dir}
    install -m 0644 ${S}/${AOS_DISK_CONFIG} ${D}${aos_opt_dir}/aosdisk.cfg

    # set integrity flags according to AOS_INTEGRITY_DISKS
    for disk in ${AOS_INTEGRITY_DISKS}; do
        sed -i "/^${disk}[[:blank:]]/s/@INTEGRITY@/1/" ${D}${aos_opt_dir}/aosdisk.cfg
    done

    sed -i "s/@INTEGRITY@/0/" ${D}${aos_opt_dir}/aosdisk.cfg
}
