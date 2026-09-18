SUMMARY = "Aggregates checkpoint_event samples in VictoriaMetrics into benchmark_result metrics"
DESCRIPTION = "Watches VictoriaMetrics for repeating windows of checkpoint_event samples (e.g. one \
AosCore deployment cycle) and publishes each window's aggregated elapsed-time metrics back to \
VictoriaMetrics as benchmark_result samples, so they show up in Grafana's Benchmark Results table \
without anyone having to separately run report_timing.py by hand. Entirely config-driven - see \
benchmark-results-publisher.yml - nothing in the script itself names a specific service, checkpoint \
text, or event; the shipped default config happens to describe AosCore's own Operational Speed \
checkpoints. Runs once, on the main node only (see aos-image.inc's IMAGE_INSTALL:append:aos-main-node), \
since VictoriaMetrics is a single shared store and watching from more than one place at once would \
double-detect and double-publish every window."

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://benchmark_results_publisher.py \
    file://benchmark-results-publisher.service \
    file://benchmark-results-publisher.yml \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "benchmark-results-publisher.service"

RDEPENDS:${PN} += " \
    python3-core \
    python3-pyyaml \
"

FILES:${PN} += " \
    ${libexecdir}/${BPN} \
    ${systemd_system_unitdir} \
    ${sysconfdir}/benchmark-results-publisher \
"

CONFFILES:${PN} += " \
    ${sysconfdir}/benchmark-results-publisher/benchmark-results-publisher.yml \
"

do_install() {
    install -d ${D}${libexecdir}/${BPN}
    install -m 0755 ${WORKDIR}/benchmark_results_publisher.py \
        ${D}${libexecdir}/${BPN}/benchmark_results_publisher.py

    install -d ${D}${systemd_system_unitdir}
    # AOS_NODE_HOSTNAME is the same variable event-exporter.bb uses for its own --node - see
    # benchmark-results-publisher.service's own comment on why this can't just be a literal "main".
    sed -e 's|@NODE@|${AOS_NODE_HOSTNAME}|' \
        ${WORKDIR}/benchmark-results-publisher.service > ${D}${systemd_system_unitdir}/benchmark-results-publisher.service

    install -d ${D}${sysconfdir}/benchmark-results-publisher
    install -m 0644 ${WORKDIR}/benchmark-results-publisher.yml \
        ${D}${sysconfdir}/benchmark-results-publisher/benchmark-results-publisher.yml
}
