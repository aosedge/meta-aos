SUMMARY = "Prometheus exporter for AosCore app instance cgroup CPU/memory usage"
DESCRIPTION = "Reads the cgroup v2 accounting files AosCore's own launcher::Monitoring class reads \
(cpu.stat, memory.current) directly, since app instances run as crun containers that \
process-exporter can't identify (their cmdline carries no instance ID) and treydock/cgroup_exporter \
doesn't fit AosCore's cgroup path depth (confirmed on a real target)."

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://cgroup_exporter.py \
    file://cgroup-exporter.service \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "cgroup-exporter.service"

RDEPENDS:${PN} += " \
    python3-core \
"

FILES:${PN} += " \
    ${libexecdir}/${BPN} \
    ${systemd_system_unitdir} \
"

do_install() {
    install -d ${D}${libexecdir}/${BPN}
    install -m 0755 ${WORKDIR}/cgroup_exporter.py ${D}${libexecdir}/${BPN}/cgroup_exporter.py

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/cgroup-exporter.service ${D}${systemd_system_unitdir}
}
