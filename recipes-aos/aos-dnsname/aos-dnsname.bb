DESCRIPTION = "DNS name CNI plugin"

GO_IMPORT = "github.com/aoscloud/aos_cni_dns"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "develop"
SRCREV = "${AUTOREV}"
SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

inherit go
inherit goarch

# embed version
GO_LDFLAGS += '-ldflags="-X github.com/containernetworking/plugins/pkg/utils/buildversion.BuildVersion=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always`"'

FILES:${PN} = "${libexecdir}/cni"

RDEPENDS:${PN} += "\
    dnsmasq \
"

# WA to support go install for v 1.18

GO_LINKSHARED = ""

do_compile:prepend() {
    cd ${GOPATH}/src/${GO_IMPORT}/
}

do_install() {
    localbindir="${libexecdir}/cni"

    install -d ${D}${localbindir}
    install -m 755 ${B}/${GO_BUILD_BINDIR}/dnsname ${D}${localbindir}
}
