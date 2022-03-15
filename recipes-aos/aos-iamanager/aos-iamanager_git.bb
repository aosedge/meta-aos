DESCRIPTION = "AOS Identity and Access Manager"

GO_IMPORT = "github.com/aoscloud/aos_iamanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "e925d4364c1c73b2ea3c3e18ba8636eca7033c59"


SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

inherit go

AOS_IAM_CERT_MODULES ??= ""
AOS_IAM_IDENT_MODULES ??= ""

# SM crashes if dynamic link selected, disable dynamic link till the problem is solved
GO_LINKSHARED = ""

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always` ${GO_RPATH} ${GO_LINKMODE} -extldflags '${GO_EXTLDFLAGS}'"'

# this flag is requied when GO_LINKSHARED is enabled
# LDFLAGS += "-lpthread"

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

RDEPENDS_${PN} += "\
    ca-certificates \
    openssl \
"

RDEPENDS_${PN}-dev += " bash make"
RDEPENDS_${PN}-staticdev += " bash make"

addtask prepare_cert_modules after do_unpack before do_compile
addtask prepare_ident_modules after do_unpack before do_compile