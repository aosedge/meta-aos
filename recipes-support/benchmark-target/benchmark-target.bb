SUMMARY = "Groups the benchmark sidecar services under a single systemd target"

DESCRIPTION = "benchmark.target Wants=/After= every benchmark exporter (node/process/cgroup/event, \
plus VictoriaMetrics on the main node), so other units can order themselves after the whole \
benchmark stack with a single After=benchmark.target instead of listing each exporter."

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://benchmark.target.in \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "benchmark.target"

FILES:${PN} = " \
    ${systemd_system_unitdir} \
"

# node/process/cgroup/event exporters run on every node; VictoriaMetrics only runs on the main
# node (see aos-image.inc) - picked via the :aos-main-node/:aos-secondary-node OVERRIDES layer.conf
# appends from AOS_MAIN_NODE, the same mechanism event-exporter.bb uses for UNIT_ARGS.
BENCHMARK_SERVICES = "node-exporter.service process-exporter.service cgroup-exporter.service event-exporter.service"
BENCHMARK_SERVICES:aos-main-node = "node-exporter.service process-exporter.service cgroup-exporter.service event-exporter.service victoria-metrics.service"

do_install() {
    install -d ${D}${systemd_system_unitdir}
    sed \
        -e 's|@BENCHMARK_SERVICES@|${BENCHMARK_SERVICES}|' \
        ${WORKDIR}/benchmark.target.in > ${D}${systemd_system_unitdir}/benchmark.target
}
