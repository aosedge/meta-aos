FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI += "file://config.yaml"

# k3s is installed for the Aos-vs-Podman-vs-k3s benchmark (DISTRO_FEATURE "benchmark") only, and is
# started by hand for the k3s runs. Enabling it at boot would leave a Kubernetes control plane
# running (etcd/sqlite, apiserver, controllers, kubelet, embedded containerd) during the AosCore and
# Podman measurements and skew them.
SYSTEMD_AUTO_ENABLE:${PN}-server = "disable"

# Install k3s and its links (kubectl, crictl) into /usr/bin instead of the recipe's /usr/local/bin.
# /usr/bin is on every PATH, including the fixed one sshd gives non-interactive "ssh host command"
# sessions (/usr/bin:/bin:/usr/sbin:/sbin), which /usr/local/bin isn't.
BIN_PREFIX = "${exec_prefix}"

# The stock unit Requires=/After= the standalone containerd.service. k3s runs its own embedded
# containerd, so that would only start a second, unused containerd daemon next to it.
do_install:append() {
    if ${@bb.utils.contains('DISTRO_FEATURES', 'systemd', 'true', 'false', d)}; then
        sed -i -e '/^Requires=containerd.service$/d' -e '/^After=containerd.service$/d' \
            ${D}${systemd_system_unitdir}/k3s.service

        # The recipe's own sed only rewrites the Exec* lines it starts with; the k3s-killall.sh path
        # in ExecStopPost's continuation line still says /usr/local/bin.
        sed -i 's#/usr/local/bin/#${bindir}/#g' ${D}${systemd_system_unitdir}/k3s.service

        # The stock unit has KillMode=process: stopping it only kills "k3s server", not what it
        # launched. Upstream k3s embeds containerd, which exits with it, but here it is the
        # external containerd binary, which would be left running (re-parented to PID 1) after
        # "systemctl stop k3s". Stop the whole service cgroup, so a stop really returns the unit to
        # its no-k3s state before an AosCore or Podman run.
        sed -i 's/^KillMode=process$/KillMode=control-group/' ${D}${systemd_system_unitdir}/k3s.service

        # The /etc symlinks below point into /var/lib/rancher; k3s needs those targets to exist
        # before it starts (it can't create a directory through a dangling symlink).
        sed -i '0,/^ExecStartPre=/s||ExecStartPre=/bin/mkdir -p /var/lib/rancher/k3s /var/lib/rancher/node\nExecStartPre=|' \
            ${D}${systemd_system_unitdir}/k3s.service
    fi

    install -D -m 0644 ${WORKDIR}/config.yaml ${D}${sysconfdir}/rancher/k3s/config.yaml

    # The rootfs (and so /etc) is read-only, but k3s writes its kubeconfig to /etc/rancher/k3s/k3s.yaml
    # and the node password to /etc/rancher/node/. Redirect both to the writable /var/lib/rancher; k3s
    # and kubectl keep using their default paths.
    ln -sf /var/lib/rancher/k3s/k3s.yaml ${D}${sysconfdir}/rancher/k3s/k3s.yaml
    ln -sfn /var/lib/rancher/node ${D}${sysconfdir}/rancher/node
}

FILES:${PN}-server += " \
    ${sysconfdir}/rancher/k3s/config.yaml \
    ${sysconfdir}/rancher/k3s/k3s.yaml \
    ${sysconfdir}/rancher/node \
"
