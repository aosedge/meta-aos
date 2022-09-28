DESCRIPTION = "AOS Communication Manager"

GO_IMPORT = "github.com/aoscloud/aos_communicationmanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "7fe966717ef72b736e9bcffa4ffb927777fdb822"

SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

inherit go
inherit goarch

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always`"'

DEPENDS = "systemd"

RDEPENDS_${PN} += "\
    ca-certificates \
    openssl \
"

RDEPENDS_${PN}-dev += " bash make"
RDEPENDS_${PN}-staticdev += " bash make"

INSANE_SKIP_${PN} = "textrel"

# WA to support go install for v 1.18

GO_LINKSHARED = ""

do_compile_prepend() {
    cd ${GOPATH}/src/${GO_IMPORT}/
}
