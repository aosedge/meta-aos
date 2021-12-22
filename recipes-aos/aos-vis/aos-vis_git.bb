DESCRIPTION = "AOS VIS"

GO_IMPORT = "aos_vis"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "37168162d461f7813305609c72c4fe168f2cdfab"
SRC_URI = "git://git@github.com/aoscloud/${GO_IMPORT}.git;branch=${BRANCH};protocol=ssh"

inherit go

AOS_VIS_PLUGINS ??= ""

# SM crashes if dynamic link selected, disable dynamic link till the problem is solved
GO_LINKSHARED = ""

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always` ${GO_RPATH} ${GO_LINKMODE} -extldflags '${GO_EXTLDFLAGS}'"'

do_prepare_adapters() {
    if [ -z "${AOS_VIS_PLUGINS}" ]; then
        exit 0
    fi

    file="${S}/src/${GO_IMPORT}/plugins/plugins.go"

    echo 'package plugins' > ${file}
    echo 'import (' >> ${file}

    for plugin in ${AOS_VIS_PLUGINS}; do
        echo "\t_ \"aos_vis/${plugin}\"" >> ${file}
    done

    echo ')' >> ${file}
}

RDEPENDS_${PN} += "\
    ca-certificates \
    openssl \
"

RDEPENDS_${PN}-dev += " bash make"
RDEPENDS_${PN}-staticdev += " bash make"

addtask prepare_adapters after do_unpack before do_compile
