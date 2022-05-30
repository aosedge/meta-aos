DESCRIPTION = "AOS Service Manager"

GO_IMPORT = "github.com/aoscloud/aos_servicemanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "05873a13ae992187da4aef61e00bd2a77400a4f8"
SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

inherit go
inherit goarch

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always`"'

DEPENDS = "systemd"

RDEPENDS_${PN} += "\
    ca-certificates \
    iptables \
    openssl \
    quota \
    cni \
    aos-firewall \
    aos-dnsname \
"

AOS_RUNNER ??= "runc"

RDEPENDS_${PN} += " ${@bb.utils.contains("AOS_RUNNER", "runc", " virtual/runc", "${AOS_RUNNER}", d)}"

RDEPENDS_${PN}-dev += " bash make"
RDEPENDS_${PN}-staticdev += " bash make"

INSANE_SKIP_${PN} = "textrel"

do_compile() {
    cd ${S}/src/${GO_IMPORT}
    ${GO} build -o ${B}/bin/aos_servicemanager
}
