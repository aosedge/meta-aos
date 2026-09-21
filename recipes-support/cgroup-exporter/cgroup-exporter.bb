SUMMARY = "Prometheus exporter for container/instance cgroup CPU/memory usage"
DESCRIPTION = "Reads cgroup v2 accounting files (cpu.stat, memory.current) directly for whichever \
cgroup paths /etc/cgroup-exporter/cgroups.yml lists, since app instances/containers run as crun/ \
runc/conmon-supervised processes that process-exporter can't identify (their cmdline carries no \
instance/container ID) and treydock/cgroup_exporter hardcodes a path depth that doesn't fit every \
runtime's cgroup layout (confirmed on a real target). Not tied to any one container runtime - \
which cgroup paths count is entirely config-driven; ships with entries for AosCore app \
instances, rootful Podman containers and k3s pods (and the k3s service's own cgroup)."

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://cgroup_exporter.py \
    file://cgroup-exporter.service \
    file://cgroup-exporter.yml \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "cgroup-exporter.service"

RDEPENDS:${PN} += " \
    python3-core \
    python3-pyyaml \
"

FILES:${PN} += " \
    ${libexecdir}/${BPN} \
    ${systemd_system_unitdir} \
    ${sysconfdir}/cgroup-exporter \
"

CONFFILES:${PN} += " \
    ${sysconfdir}/cgroup-exporter/cgroups.yml \
"

do_install() {
    install -d ${D}${libexecdir}/${BPN}
    install -m 0755 ${WORKDIR}/cgroup_exporter.py ${D}${libexecdir}/${BPN}/cgroup_exporter.py

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/cgroup-exporter.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/cgroup-exporter
    install -m 0644 ${WORKDIR}/cgroup-exporter.yml ${D}${sysconfdir}/cgroup-exporter/cgroups.yml
}
