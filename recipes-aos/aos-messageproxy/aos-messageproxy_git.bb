DESCRIPTION = "AOS Message Proxy"

GO_IMPORT = "github.com/aosedge/aos_message_proxy"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

BRANCH = "main"
SRCREV = "b4f63e6b1c952ee3870b0671ff7a4395809fadb1"

SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

SRC_URI += " \
    file://aos_messageproxy.cfg \
    file://aos-messageproxy.service \
    file://aos-messageproxy-provisioning.service \
    file://aos-target.conf \
    file://aos-cm-service.conf \
"

FILES:${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
"

inherit go goarch systemd

SYSTEMD_SERVICE:${PN} = "aos-messageproxy.service aos-messageproxy-provisioning.service"

DEPENDS = "xen-tools"
RDEPENDS:${PN} = "xen-tools-libxenvchan"

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always`"'

# WA to support go install for v 1.18

GO_LINKSHARED = ""

do_compile:prepend() {
    cd ${GOPATH}/src/${GO_IMPORT}/
}

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_messageproxy.cfg")

    with open(file_name) as f:
        data = json.load(f)

    node_hostname = d.getVar("AOS_NODE_HOSTNAME")
    main_node_hostname = d.getVar("AOS_MAIN_NODE_HOSTNAME")

    # Update IAM servers

    data["IAMPublicServerURL"] = node_hostname+":8090"

    # Update CM server

    data["CMServerURL"] = main_node_hostname+":8093"

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
}

do_install:append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_messageproxy.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-messageproxy.service ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-messageproxy-provisioning.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf
}

do_install:append:aos-main-node() {
    install -d ${D}${sysconfdir}/systemd/system/aos-messageproxy.service.d
    install -m 0644 ${WORKDIR}/aos-cm-service.conf ${D}${sysconfdir}/systemd/system/aos-messageproxy.service.d/10-aos-cm-service.conf
}

addtask update_config after do_install before do_package
