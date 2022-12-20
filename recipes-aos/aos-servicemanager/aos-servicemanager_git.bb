DESCRIPTION = "AOS Service Manager"

GO_IMPORT = "github.com/aoscloud/aos_servicemanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "3e6602d95dd9d4ee2240d25a858d37d00752ed20"
SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

SRC_URI += " \
    file://aos_servicemanager.cfg \
    file://aos-servicemanager.service \
    file://aos-target.conf \
"

inherit go goarch systemd

SYSTEMD_SERVICE_${PN} = "aos-servicemanager.service"

MIGRATION_SCRIPTS_PATH = "${base_prefix}/usr/share/aos/sm/migration"
AOS_RUNNER ??= "crun"

FILES_${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
    ${MIGRATION_SCRIPTS_PATH} \
"

DEPENDS = "systemd"

RDEPENDS_${PN} += "\
    aos-rootca \
    iptables \
    quota \
    cni \
    aos-firewall \
    aos-dnsname \
    ${@bb.utils.contains("AOS_RUNNER", "runc", " virtual/runc", "${AOS_RUNNER}", d)} \
"

RRECOMMENDS_${PN} += " \
    kernel-module-bridge \
    kernel-module-nf-conncount \
    kernel-module-nfnetlink \
    kernel-module-overlay \
    kernel-module-veth \
    kernel-module-xt-addrtype \
    kernel-module-xt-comment \
    kernel-module-xt-conntrack \
    kernel-module-xt-masquerade \
"

RDEPENDS_${PN}-dev += " bash make"
RDEPENDS_${PN}-staticdev += " bash make"

INSANE_SKIP_${PN} = "textrel"

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always`"'

# WA to support go install for v 1.18

GO_LINKSHARED = ""

do_compile_prepend() {
    cd ${GOPATH}/src/${GO_IMPORT}/
}

do_install_append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_servicemanager.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-servicemanager.service ${D}${systemd_system_unitdir}
    install -m 0644 ${S}/src/${GO_IMPORT}/runner/aos-service@.service ${D}${systemd_system_unitdir}
    sed -i 's/runc/${AOS_RUNNER}/g' ${D}${systemd_system_unitdir}/aos-service@.service

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf

    install -d ${D}${MIGRATION_SCRIPTS_PATH}
    source_migration_path="/src/${GO_IMPORT}/database/migration"
    if [ -d ${S}${source_migration_path} ]; then
        install -m 0644 ${S}${source_migration_path}/* ${D}${MIGRATION_SCRIPTS_PATH}
    fi
}

pkg_postinst_${PN}() {
    # Add aossm to /etc/hosts
    if ! grep -q 'aossm' $D${sysconfdir}/hosts ; then
        echo '127.0.0.1	aossm' >> $D${sysconfdir}/hosts
    fi
}
