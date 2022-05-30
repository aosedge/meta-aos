DESCRIPTION = "AOS Update Manager"

GO_IMPORT = "github.com/aoscloud/aos_updatemanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "837ad2f00a86ef714f0225ae2912fe5dd2333c83"
SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

inherit go
inherit goarch

AOS_UM_UPDATE_MODULES ??= ""

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always`"'

RDEPENDS_${PN}-dev += " bash make"
RDEPENDS_${PN}-staticdev += " bash make"

INSANE_SKIP_${PN} = "textrel"

do_compile() {
    cd ${S}/src/${GO_IMPORT}
    ${GO} build -o ${B}/bin/aos_updatemanager
}

do_prepare_modules() {
    if [ -z "${AOS_UM_UPDATE_MODULES}" ]; then
        exit 0
    fi

    file="${S}/src/${GO_IMPORT}/updatemodules/modules.go"

    echo 'package updatemodules' > ${file}
    echo 'import (' >> ${file}

    for module in ${AOS_UM_UPDATE_MODULES}; do
        echo "\t_ \"${GO_IMPORT}/${module}\"" >> ${file}
    done

    echo ')' >> ${file}
}

addtask prepare_modules after do_unpack before do_compile
