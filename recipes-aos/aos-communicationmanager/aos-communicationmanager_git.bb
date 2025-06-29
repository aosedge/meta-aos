DESCRIPTION = "AOS Communication Manager"

GO_IMPORT = "github.com/aosedge/aos_communicationmanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "11a4ef530cf3a0357ffa0d9e45c342c9891b9222"

SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

SRC_URI += " \
    file://aos_communicationmanager.cfg \
    file://aos-communicationmanager.service \
    file://aos-target.conf \
    file://aos-dirs-service.conf \
"

inherit go goarch systemd

SYSTEMD_SERVICE:${PN} = "aos-communicationmanager.service"

MIGRATION_SCRIPTS_PATH = "${base_prefix}/usr/share/aos/cm/migration"

FILES:${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
    ${MIGRATION_SCRIPTS_PATH} \
"

DEPENDS = "systemd"

RDEPENDS:${PN} += " \
    aos-rootca \
    nfs-exports \
"

RDEPENDS:${PN}-dev += " bash make"
RDEPENDS:${PN}-staticdev += " bash make"

INSANE_SKIP:${PN} = "textrel"

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always`"'

# WA to support go install for v 1.18

GO_LINKSHARED = ""

RRECOMMENDS:${PN} += " \
    kernel-module-quota-v1 \
    kernel-module-quota-v2 \
    kernel-module-quota-tree \
"

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_communicationmanager.cfg")

    with open(file_name) as f:
        data = json.load(f)

    node_hostname = d.getVar("AOS_NODE_HOSTNAME")
 
    # Update IAM servers
    
    data["IAMProtectedServerURL"]= node_hostname+":8089"
    data["IAMPublicServerURL"] = node_hostname+":8090"

    # Update DNS IP

    dns_ip = d.getVar("AOS_DNS_IP")
    if dns_ip:
        data["DNSIP"] = dns_ip

    main_node_hostname = d.getVar("AOS_MAIN_NODE_HOSTNAME")

    # Update SM controller
    sm_controller = data["SMController"]
    sm_controller["FileServerURL"] = main_node_hostname+":8094"

    # Update CM controller
    um_controller = data["UMController"]
    um_controller["FileServerURL"] = main_node_hostname+":8092"

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
}

do_compile:prepend() {
    cd ${GOPATH}/src/${GO_IMPORT}/
}

do_install:append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_communicationmanager.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-communicationmanager.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf

    install -d ${D}${sysconfdir}/systemd/system/aos-communicationmanager.service.d
    install -m 0644 ${WORKDIR}/aos-dirs-service.conf ${D}${sysconfdir}/systemd/system/aos-communicationmanager.service.d/10-aos-dirs-service.conf

    install -d ${D}${MIGRATION_SCRIPTS_PATH}
    source_migration_path="/src/${GO_IMPORT}/database/migration"
    if [ -d ${S}${source_migration_path} ]; then
        install -m 0644 ${S}${source_migration_path}/* ${D}${MIGRATION_SCRIPTS_PATH}
    fi
}

addtask update_config after do_install before do_package
