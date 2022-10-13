DESCRIPTION = "AOS Identity and Access Manager"

GO_IMPORT = "github.com/aoscloud/aos_iamanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "b21c12822b8675efffa330909f559483c427fb63"

SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

SRC_URI += " \
    file://aos_iamanager.cfg \
    file://aos-iamanager.service \
"

inherit go goarch systemd

SYSTEMD_SERVICE_${PN} = "aos-iamanager.service"

AOS_IAM_CERT_MODULES ??= "certhandler/modules/swmodule"
AOS_IAM_IDENT_MODULES ??= "identhandler/modules/fileidentifier"

MIGRATION_SCRIPTS_PATH = "${base_prefix}/usr/share/aos/iam/migration"

FILES_${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
    ${MIGRATION_SCRIPTS_PATH} \
"

RDEPENDS_${PN} += " \
    aos-rootca \
    aos-provfirewall \
    aos-provfinish \
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

do_prepare_cert_modules() {
    if [ -z "${AOS_IAM_CERT_MODULES}" ]; then
        exit 0
    fi

    file="${S}/src/${GO_IMPORT}/certhandler/modules/modules.go"

    echo 'package certmodules' > ${file}
    echo 'import (' >> ${file}

    for module in ${AOS_IAM_CERT_MODULES}; do
        echo "\t_ \"${GO_IMPORT}/${module}\"" >> ${file}
    done

    echo ')' >> ${file}
}

do_prepare_ident_modules() {
    if [ -z "${AOS_IAM_IDENT_MODULES}" ]; then
        exit 0
    fi

    file="${S}/src/${GO_IMPORT}/identhandler/modules/modules.go"

    echo 'package identmodules' > ${file}
    echo 'import (' >> ${file}

    for module in ${AOS_IAM_IDENT_MODULES}; do
        echo "\t_ \"${GO_IMPORT}/${module}\"" >> ${file}
    done

    echo ')' >> ${file}
}

do_install_append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_iamanager.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-iamanager.service ${D}${systemd_system_unitdir}

    install -d ${D}${MIGRATION_SCRIPTS_PATH}
    source_migration_path="/src/${GO_IMPORT}/database/migration"
    if [ -d ${S}${source_migration_path} ]; then
        install -m 0644 ${S}${source_migration_path}/* ${D}${MIGRATION_SCRIPTS_PATH}
    fi
}

pkg_postinst_${PN}() {
    # Add aosiam to /etc/hosts
    if ! grep -q 'aosiam' $D${sysconfdir}/hosts ; then
        echo '127.0.0.1	aosiam' >> $D${sysconfdir}/hosts
    fi
}

addtask prepare_cert_modules after do_unpack before do_compile
addtask prepare_ident_modules after do_unpack before do_compile
