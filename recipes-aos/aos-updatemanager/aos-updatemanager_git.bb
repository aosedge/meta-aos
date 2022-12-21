FILESEXTRAPATHS_prepend := "${THISDIR}/files:"

DESCRIPTION = "AOS Update Manager"

GO_IMPORT = "github.com/aoscloud/aos_updatemanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "cf2d80972e44579d95cc431aedd42f1fb830a784"
SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

SRC_URI += " \
    file://aos_updatemanager.cfg \
    file://aos-updatemanager.service \
    file://aos-target.conf \
"

inherit go goarch systemd

SYSTEMD_SERVICE_${PN} = "aos-updatemanager.service"

AOS_UM_UPDATE_MODULES ?= " \
    updatemodules/testmodule \
"

MIGRATION_SCRIPTS_PATH = "${base_prefix}/usr/share/aos/um/migration"

FILES_${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
    ${MIGRATION_SCRIPTS_PATH} \
"

DEPENDS_append = " \
    pkgconfig-native \
    util-linux \
    efivar \
"

RDEPENDS_${PN} = " \
    aos-rootca \
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

do_prepare_modules() {
    file="${S}/src/${GO_IMPORT}/updatemodules/modules.go"

    echo 'package updatemodules' > ${file}
    echo 'import (' >> ${file}

    for module in ${AOS_UM_UPDATE_MODULES}; do
        echo "\t_ \"${GO_IMPORT}/${module}\"" >> ${file}
    done

    echo ')' >> ${file}
}

do_install_append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_updatemanager.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-updatemanager.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf

    install -d ${D}${MIGRATION_SCRIPTS_PATH}
    source_migration_path="src/${GO_IMPORT}/database/migration"
    if [ -d ${S}/${source_migration_path} ]; then
        install -m 0644 ${S}/${source_migration_path}/* ${D}${MIGRATION_SCRIPTS_PATH}
    fi
}

addtask prepare_modules after do_unpack before do_compile
