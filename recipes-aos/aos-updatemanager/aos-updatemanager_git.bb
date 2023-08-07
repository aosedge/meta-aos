FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

DESCRIPTION = "AOS Update Manager"

GO_IMPORT = "github.com/aoscloud/aos_updatemanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "develop"
SRCREV = "${AUTOREV}"

SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

SRC_URI += " \
    file://aos_updatemanager.cfg \
    file://aos-updatemanager.service \
    file://aos-target.conf \
    file://aos-dirs-service.conf \
    file://aos-cm-service.conf \
"

inherit go goarch systemd

SYSTEMD_SERVICE:${PN} = "aos-updatemanager.service"

AOS_UM_UPDATE_MODULES ?= " \
    updatemodules/testmodule \
"

MIGRATION_SCRIPTS_PATH = "${base_prefix}/usr/share/aos/um/migration"

FILES:${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
    ${MIGRATION_SCRIPTS_PATH} \
"

DEPENDS:append = " \
    pkgconfig-native \
    util-linux \
    efivar \
"

RDEPENDS:${PN} = " \
    aos-rootca \
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

do_prepare_modules() {
    file="${S}/src/${GO_IMPORT}/updatemodules/modules.go"

    echo 'package updatemodules' > ${file}
    echo 'import (' >> ${file}

    for module in ${AOS_UM_UPDATE_MODULES}; do
        echo "\t_ \"${GO_IMPORT}/${module}\"" >> ${file}
    done

    echo ')' >> ${file}
}

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_updatemanager.cfg")

    with open(file_name) as f:
        data = json.load(f)

    node_hostname = d.getVar("AOS_NODE_HOSTNAME")
    main_node_hostname = d.getVar("AOS_MAIN_NODE_HOSTNAME")
 
    # Update IAM servers
    
    data["IAMPublicServerURL"] = node_hostname+":8090"

    # Update CM server

    data["CMServerURL"] = main_node_hostname+":8091"

    # Update component IDs

    comp_prefix = d.getVar("AOS_UM_COMPONENT_PREFIX")

    for update_module in data["UpdateModules"]:
        update_module["ID"] = comp_prefix+update_module["ID"]

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
}

do_compile[vardeps] += "AOS_UM_COMPONENT_PREFIX"

do_install:append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_updatemanager.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-updatemanager.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf

    install -d ${D}${sysconfdir}/systemd/system/aos-updatemanager.service.d
    install -m 0644 ${WORKDIR}/aos-dirs-service.conf ${D}${sysconfdir}/systemd/system/aos-updatemanager.service.d/20-aos-dirs-service.conf

    install -d ${D}${MIGRATION_SCRIPTS_PATH}
    source_migration_path="src/${GO_IMPORT}/database/migration"
    if [ -d ${S}/${source_migration_path} ]; then
        install -m 0644 ${S}/${source_migration_path}/* ${D}${MIGRATION_SCRIPTS_PATH}
    fi
}

do_install:append:aos-main-node() {
    install -d ${D}${sysconfdir}/systemd/system/aos-updatemanager.service.d
    install -m 0644 ${WORKDIR}/aos-cm-service.conf ${D}${sysconfdir}/systemd/system/aos-updatemanager.service.d/10-aos-cm-service.conf
}

addtask update_config after do_install before do_package
addtask prepare_modules after do_unpack before do_compile
