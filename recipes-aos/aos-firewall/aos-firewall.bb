DESCRIPTION = "AOS fierwall CNI plugin"

GO_IMPORT = "github.com/aoscloud/aos_cni_firewall"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "c6b943c8d2192a66306397552d2a8d1fb0ffb8a0"
SRC_URI = "git://${GO_IMPORT}.git;branch=${BRANCH};protocol=https"

inherit go
inherit goarch

# embed version
GO_LDFLAGS += '-ldflags="-X github.com/containernetworking/plugins/pkg/utils/buildversion.BuildVersion=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always`"'

FILES_${PN} = "${libexecdir}/cni"

do_compile() {
    cd ${S}/src/${GO_IMPORT}
    ${GO} build -o ${B}/bin/aos-firewall ./plugins/meta/aos-firewall
}

do_install() {
    localbindir="${libexecdir}/cni"

    install -d ${D}${localbindir}
    install -m 755 ${B}/bin/aos-firewall ${D}${localbindir}
}
