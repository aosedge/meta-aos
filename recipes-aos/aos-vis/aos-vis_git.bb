DESCRIPTION = "AOS VIS"

GO_IMPORT = "github.com/aoscloud/aos_vis"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "ca63a713f82950efda66ddf824c193cff3b13fd4"
SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

inherit go
inherit goarch

AOS_VIS_PLUGINS ??= ""

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always`"'

RDEPENDS_${PN} += "\
    ca-certificates \
    openssl \
"

RDEPENDS_${PN}-dev += " bash make"
RDEPENDS_${PN}-staticdev += " bash make"

do_compile() {
    cd ${S}/src/${GO_IMPORT}
    ${GO} build -o ${B}/bin/aos_vis
}

do_prepare_adapters() {
    if [ -z "${AOS_VIS_PLUGINS}" ]; then
        exit 0
    fi

    file="${S}/src/${GO_IMPORT}/plugins/plugins.go"

    echo 'package plugins' > ${file}
    echo 'import (' >> ${file}

    for plugin in ${AOS_VIS_PLUGINS}; do
        echo "\t_ \"${GO_IMPORT}/${plugin}\"" >> ${file}
    done

    echo ')' >> ${file}
}

addtask prepare_adapters after do_unpack before do_compile
