hostname = "${AOS_NODE_HOSTNAME}"

do_install:append() {
    # remove /run from fstab, run is mounted in initramfs
    sed -i "\:[[:blank:]]*/run:d" ${D}${sysconfdir}/fstab

    # add Aos partitions
    echo "# Aos partitions">> ${D}${sysconfdir}/fstab
    echo '/dev/aosvg/workdirs  /var/aos/workdirs   ext4 defaults,nofail,noatime,x-systemd.automount'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab
}

do_install:append:aos-main-node() {
    # add Aos partitions
   echo '/dev/aosvg/downloads /var/aos/downloads ext4 defaults,nofail,noatime,x-systemd.automount'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab

   echo '/dev/aosvg/storages /var/aos/storages ext4 ' \
'defaults,nofail,noatime,usrjquota=aquota.user,jqfmt=vfsv0,x-systemd.automount'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab

    echo '/dev/aosvg/states /var/aos/states ext4 ' \
'defaults,nofail,noatime,usrjquota=aquota.user,jqfmt=vfsv0,x-systemd.automount'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab
}

do_install:append:aos-secondary-node() {
    # add Aos partitions
   echo '${AOS_MAIN_NODE_HOSTNAME}:/var/aos/storages /var/aos/storages nfs4 defaults,nofail,noatime,'\
'retrans=0,timeo=100,x-systemd.automount'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab

    echo '${AOS_MAIN_NODE_HOSTNAME}:/var/aos/states /var/aos/states nfs4 defaults,nofail,noatime,'\
'retrans=0,timeo=100,x-systemd.automount'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab
}
