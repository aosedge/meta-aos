DESCRIPTION = "Starts multiple iperf3/sockperf servers, bound to a given address, for the network \
bandwidth/latency benchmarks' service-to-unit/service-to-external-host scenarios"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://iperf3-servers.sh \
    file://sockperf-servers.sh \
"

S = "${WORKDIR}"

FILES:${PN} = " \
    ${aos_opt_dir} \
"

RDEPENDS:${PN} = " \
    bash \
    iperf3 \
    sockperf \
"

do_install() {
    install -d ${D}${aos_opt_dir}/benchmark
    install -m 0755 ${S}/iperf3-servers.sh ${D}${aos_opt_dir}/benchmark
    install -m 0755 ${S}/sockperf-servers.sh ${D}${aos_opt_dir}/benchmark
}
