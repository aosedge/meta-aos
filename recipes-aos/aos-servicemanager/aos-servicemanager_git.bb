DESCRIPTION = "AOS Service Manager"

GO_IMPORT = "github.com/aosedge/aos_servicemanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "03d9887a9e9a0e60c9beef2b7cfa1f6dd4ab99a1"

SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

SRC_URI += " \
    file://aos_servicemanager.cfg \
    file://aos-servicemanager.service \
    file://aos-target.conf \
    file://aos-dirs-service.conf \
    file://aos-cm-service.conf \
"

inherit go goarch systemd

SYSTEMD_SERVICE:${PN} = "aos-servicemanager.service"

MIGRATION_SCRIPTS_PATH = "${base_prefix}/usr/share/aos/sm/migration"

FILES:${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
    ${MIGRATION_SCRIPTS_PATH} \
"

DEPENDS = "systemd"

VIRTUAL_RUNC = "${@bb.utils.contains('LAYERSERIES_CORENAMES', 'dunfell', 'virtual/runc', 'virtual-runc', d)}"

RDEPENDS:${PN} += " \
    aos-rootca \
    iptables \
    quota \
    cni \
    aos-firewall \
    aos-dnsname \
    ${@bb.utils.contains("AOS_RUNNER", "runc", "${VIRTUAL_RUNC}", "${AOS_RUNNER}", d)} \
"

RDEPENDS:${PN}:append:aos-secondary-node = " \
    packagegroup-core-nfs-client \
"

RRECOMMENDS:${PN} += " \
    kernel-module-8021q \
    kernel-module-bridge \
    kernel-module-ifb \
    kernel-module-nf-conncount \
    kernel-module-nfnetlink \
    kernel-module-overlay \
    kernel-module-veth \
    kernel-module-vxlan \
    kernel-module-xt-addrtype \
    kernel-module-xt-comment \
    kernel-module-xt-conntrack \
    kernel-module-xt-masquerade \
    kernel-module-xt-tcpudp \
    kernel-module-sch-tbf \
"

RDEPENDS:${PN}-dev += " bash make"
RDEPENDS:${PN}-staticdev += " bash make"

INSANE_SKIP:${PN} = "textrel"

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always`"'

# WA to support go install for v 1.18

GO_LINKSHARED = ""

do_compile:prepend() {
    cd ${GOPATH}/src/${GO_IMPORT}/
}

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_servicemanager.cfg")

    with open(file_name) as f:
        data = json.load(f)

    node_hostname = d.getVar("AOS_NODE_HOSTNAME")
    main_node_hostname = d.getVar("AOS_MAIN_NODE_HOSTNAME")

    # Update IAM servers

    data["IAMProtectedServerURL"] = node_hostname+":8089"
    data["IAMPublicServerURL"] = node_hostname+":8090"

    # Update CM server

    data["CMServerURL"] = main_node_hostname+":8093"

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
}

do_install:append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_servicemanager.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-servicemanager.service ${D}${systemd_system_unitdir}
    install -m 0644 ${S}/src/${GO_IMPORT}/runner/aos-service@.service ${D}${systemd_system_unitdir}
    sed -i 's/runc/${AOS_RUNNER}/g' ${D}${systemd_system_unitdir}/aos-service@.service

    install -d ${D}${sysconfdir}/systemd/system/aos-servicemanager.service.d
    install -m 0644 ${WORKDIR}/aos-dirs-service.conf ${D}${sysconfdir}/systemd/system/aos-servicemanager.service.d/20-aos-dirs-service.conf

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf

    install -d ${D}${MIGRATION_SCRIPTS_PATH}
    source_migration_path="/src/${GO_IMPORT}/database/migration"
    if [ -d ${S}${source_migration_path} ]; then
        install -m 0644 ${S}${source_migration_path}/* ${D}${MIGRATION_SCRIPTS_PATH}
    fi
}

do_install:append:aos-main-node() {
    install -d ${D}${sysconfdir}/systemd/system/aos-servicemanager.service.d
    install -m 0644 ${WORKDIR}/aos-cm-service.conf ${D}${sysconfdir}/systemd/system/aos-servicemanager.service.d/10-aos-cm-service.conf
}

addtask update_config after do_install before do_package
