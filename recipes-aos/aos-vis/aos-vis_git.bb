DESCRIPTION = "AOS VIS"

GO_IMPORT = "github.com/aoscloud/aos_vis"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "b7aecd75aa1754fed777600a39839475afbd40b8"
SRC_URI = "git://git@${GO_IMPORT}.git;branch=${BRANCH};protocol=ssh"

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
        echo "\t_ \"${GO_IMPORT}/${plugin}\"" >> ${file}
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
