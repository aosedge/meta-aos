DESCRIPTION = "AOS Identity and Access Manager"

GO_IMPORT = "github.com/aoscloud/aos_iamanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "develop"
SRCREV = "${AUTOREV}"

SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

SRC_URI += " \
    file://aos_iamanager.cfg \
    file://aos-iamanager.service \
    file://aos-iamanager-provisioning.service \
    file://aos-target.conf \
"

inherit go goarch systemd

SYSTEMD_SERVICE:${PN} = "aos-iamanager.service aos-iamanager-provisioning.service"

AOS_IAM_CERT_MODULES ?= "certhandler/modules/swmodule"
AOS_IAM_IDENT_MODULES ?= ""

MIGRATION_SCRIPTS_PATH = "${base_prefix}/usr/share/aos/iam/migration"

FILES:${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
    ${MIGRATION_SCRIPTS_PATH} \
"

RDEPENDS:${PN} += " \
    aos-rootca \
    aos-provfinish \
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

do_prepare_cert_modules() {
    file="${S}/src/${GO_IMPORT}/certhandler/modules/modules.go"

    echo 'package certmodules' > ${file}
    echo 'import (' >> ${file}

    for module in ${AOS_IAM_CERT_MODULES}; do
        echo "\t_ \"${GO_IMPORT}/${module}\"" >> ${file}
    done

    echo ')' >> ${file}
}

do_prepare_ident_modules() {
    file="${S}/src/${GO_IMPORT}/identhandler/modules/modules.go"

    echo 'package identmodules' > ${file}
    echo 'import (' >> ${file}

    for module in ${AOS_IAM_IDENT_MODULES}; do
        echo "\t_ \"${GO_IMPORT}/${module}\"" >> ${file}
    done

    echo ')' >> ${file}
}

do_fetch[vardeps] += "AOS_NODE_ID AOS_NODE_TYPE AOS_IAM_NODES AOS_IAM_HOSTNAMES"

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_iamanager.cfg")

    with open(file_name) as f:
        data = json.load(f)

    # Set node ID and node type
    
    node_info = {
        "NodeID": d.getVar("AOS_NODE_ID"),
        "NodeType" : d.getVar("AOS_NODE_TYPE")
    }

    data = {**node_info, **data}

    # Set alternative names for server certificates

    for cert_module in data["CertModules"]:
        if "ExtendedKeyUsage" in cert_module and "serverAuth" in cert_module["ExtendedKeyUsage"]:
            cert_module["AlternativeNames"] = [d.getVar("AOS_NODE_HOSTNAME")]

    # Add remote IAM's configuration

    node_id = d.getVar("AOS_NODE_ID")
    iam_nodes = d.getVar("AOS_IAM_NODES").split()
    iam_hostnames = d.getVar("AOS_IAM_HOSTNAMES").split()

    if len(iam_nodes) > 1 or (len(iam_nodes) == 1 and node_id not in iam_nodes):
        data["RemoteIams"] = []

        for i in range(len(iam_nodes)):
            if iam_nodes[i] == node_id:
                continue

            data["RemoteIams"].append({"NodeID": iam_nodes[i], "URL": iam_hostnames[i]+":8089"})

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
}

do_install:append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_iamanager.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-iamanager.service ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-iamanager-provisioning.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf

    install -d ${D}${MIGRATION_SCRIPTS_PATH}
    source_migration_path="/src/${GO_IMPORT}/database/migration"
    if [ -d ${S}${source_migration_path} ]; then
        install -m 0644 ${S}${source_migration_path}/* ${D}${MIGRATION_SCRIPTS_PATH}
    fi
}

addtask prepare_cert_modules after do_unpack before do_compile
addtask prepare_ident_modules after do_unpack before do_compile
addtask update_config after do_install before do_package
