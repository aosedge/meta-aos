DESCRIPTION = "AOS Service Manager"

GO_IMPORT = "github.com/aoscloud/aos_servicemanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "3e6602d95dd9d4ee2240d25a858d37d00752ed20"
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

RDEPENDS_${PN} += " \
    kernel-module-bridge \
    kernel-module-nfnetlink \
    kernel-module-veth \
    kernel-module-xt-addrtype \
    kernel-module-xt-comment \
    kernel-module-xt-conntrack \
    kernel-module-xt-masquerade \
    kernel-module-overlay \
"

AOS_RUNNER ??= "crun"

RDEPENDS_${PN} += " ${@bb.utils.contains("AOS_RUNNER", "runc", " virtual/runc", "${AOS_RUNNER}", d)}"

RDEPENDS_${PN}-dev += " bash make"
RDEPENDS_${PN}-staticdev += " bash make"

INSANE_SKIP_${PN} = "textrel"

# WA to support go install for v 1.18

GO_LINKSHARED = ""

do_compile_prepend() {
    cd ${GOPATH}/src/${GO_IMPORT}/
}
