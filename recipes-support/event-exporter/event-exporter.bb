SUMMARY = "Forwards log checkpoints to VictoriaMetrics as events"
DESCRIPTION = "Tails journald for the given systemd units and pushes each line matching a regex \
from /etc/event-exporter/patterns.yml (by default, AosCore's own \"[profiling] <text>\" \
checkpoint lines, e.g. instance start/stop begin/end) to VictoriaMetrics as a checkpoint_event \
sample, so Grafana can overlay them on the same graphs that plot CPU/MEM usage collected by \
node-exporter/process-exporter/cgroup-exporter. Not AosCore-specific - which lines count as \
checkpoints is entirely config-driven, not hardcoded."

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://event_exporter.py \
    file://event-exporter.service \
    file://event-exporter.default \
    file://event-exporter.yml \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "event-exporter.service"

RDEPENDS:${PN} += " \
    python3-core \
    python3-pyyaml \
"

FILES:${PN} += " \
    ${libexecdir}/${BPN} \
    ${systemd_system_unitdir} \
    ${sysconfdir}/default \
    ${sysconfdir}/event-exporter \
"

CONFFILES:${PN} += " \
    ${sysconfdir}/default/event-exporter \
    ${sysconfdir}/event-exporter/patterns.yml \
"

# CM only runs on the main node; every node runs SM/IAM (see aos-image.inc). Picked via the
# :aos-main-node/:aos-secondary-node OVERRIDES layer.conf appends from AOS_MAIN_NODE, the same
# mechanism aos-image.inc uses for IMAGE_INSTALL:append:aos-main-node.
UNIT_ARGS = "--unit aos-sm --unit aos-iam"
UNIT_ARGS:aos-main-node = "--unit aos-cm --unit aos-sm --unit aos-iam"

do_install() {
    install -d ${D}${libexecdir}/${BPN}
    install -m 0755 ${WORKDIR}/event_exporter.py ${D}${libexecdir}/${BPN}/event_exporter.py

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/event-exporter.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/default
    sed \
        -e 's|@VICTORIA_URL@|http://${AOS_MAIN_NODE_HOSTNAME}:8428|' \
        -e 's|@NODE@|${AOS_NODE_HOSTNAME}|' \
        -e 's|@UNIT_ARGS@|${UNIT_ARGS}|' \
        ${WORKDIR}/event-exporter.default > ${D}${sysconfdir}/default/event-exporter

    install -d ${D}${sysconfdir}/event-exporter
    install -m 0644 ${WORKDIR}/event-exporter.yml ${D}${sysconfdir}/event-exporter/patterns.yml
}
