hostname = "${AOS_NODE_HOSTNAME}"
aos_disks_timeout = "30"

def aos_disk_device(d, disk):
    if disk in d.getVar('AOS_INTEGRITY_DISKS').split():
        return '/dev/mapper/aosint-' + disk

    return '/dev/aosvg/' + disk

do_install[vardeps] += "AOS_INTEGRITY_DISKS"

do_install:append() {
    # remove /run from fstab, run is mounted in initramfs
    sed -i "\:[[:blank:]]*/run:d" ${D}${sysconfdir}/fstab

    # add Aos partitions
    echo "# Aos partitions">> ${D}${sysconfdir}/fstab
    echo '${@aos_disk_device(d, 'workdirs')} /var/aos/workdirs ext4 defaults,auto,nofail,noatime,'\
'x-systemd.device-timeout=${aos_disks_timeout}'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab
}

do_install:append:aos-main-node() {
    # add Aos partitions
   echo '${@aos_disk_device(d, 'downloads')} /var/aos/downloads ext4 defaults,auto,nofail,'\
'noatime,x-systemd.device-timeout=${aos_disks_timeout}'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab

   echo '${@aos_disk_device(d, 'storages')} /var/aos/storages ext4 defaults,auto,nofail,noatime,usrquota,grpquota,'\
'noatime,x-systemd.device-timeout=${aos_disks_timeout}'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab

    echo '${@aos_disk_device(d, 'states')} /var/aos/states ext4 defaults,auto,nofail,noatime,usrquota,grpquota,'\
'x-systemd.device-timeout=${aos_disks_timeout}'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab
}

do_install:append:aos-secondary-node() {
    # add Aos partitions
   echo '${AOS_MAIN_NODE_HOSTNAME}:/storages /var/aos/storages nfs4 defaults,auto,nofail,noatime,'\
'retrans=0,timeo=100,x-systemd.device-timeout=90'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab

    echo '${AOS_MAIN_NODE_HOSTNAME}:/states /var/aos/states nfs4 defaults,auto,nofail,noatime,'\
'retrans=0,timeo=100,x-systemd.device-timeout=90'\
${@bb.utils.contains('DISTRO_FEATURES', 'selinux', ',context=system_u:object_r:aos_var_run_t:s0', '', d)} '0 0' \
   >> ${D}/${sysconfdir}/fstab
}
