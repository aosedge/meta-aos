do_install_append () {
    if ! ${@bb.utils.contains('DISTRO_FEATURES', 'read-only-rootfs', 'true', 'false', d)}; then
        exit 0
    fi

    sed -i '/HostKey/d' ${D}${sysconfdir}/ssh/sshd_config_readonly
    echo "HostKey /var/ssh/ssh_host_rsa_key" >> ${D}${sysconfdir}/ssh/sshd_config_readonly
    echo "HostKey /var/ssh/ssh_host_ecdsa_key" >> ${D}${sysconfdir}/ssh/sshd_config_readonly
    echo "HostKey /var/ssh/ssh_host_ed25519_key" >> ${D}${sysconfdir}/ssh/sshd_config_readonly
}
