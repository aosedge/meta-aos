DESCRIPTION = "AOS Message Proxy"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

BRANCH = "main"
SRCREV = "dc40f007a9ca17292c5e7c9a729cfcabda1b8ec1"

SRC_URI = "gitsm://github.com/aosedge/aos_core_mp_cpp.git;protocol=https;branch=${BRANCH}"

SRC_URI += " \
    file://aos_messageproxy.cfg \
    file://aos-messageproxy.service \
    file://aos-messageproxy-provisioning.service \
    file://aos-target.conf \
    file://aos-cm-service.conf \
"

S = "${WORKDIR}/git"

inherit autotools pkgconfig cmake systemd

DEPENDS += "poco systemd grpc grpc-native protobuf-native protobuf curl libnl"

PACKAGECONFIG ??= "${@bb.utils.contains('DISTRO_FEATURES', 'xen', 'vchan', '', d)}"
PACKAGECONFIG[vchan] = "-DWITH_VCHAN=ON,-DWITH_VCHAN=OFF,xen-tools,xen-tools-libxenvchan"

OECMAKE_GENERATOR = "Unix Makefiles"
EXTRA_OECMAKE += "-DFETCHCONTENT_FULLY_DISCONNECTED=OFF -DWITH_MBEDTLS=OFF -DWITH_OPENSSL=ON"

SYSTEMD_SERVICE:${PN} = "aos-messageproxy.service aos-messageproxy-provisioning.service"

FILES:${PN} += " \
    ${sysconfdir} \
"

do_compile[network] = "1"
do_configure[network] =  "1"

do_install:append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_messageproxy.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-messageproxy.service ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-messageproxy-provisioning.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf
}

do_install:append:aos-main-node() {
    install -d ${D}${sysconfdir}/systemd/system/aos-messageproxy.service.d
    install -m 0644 ${WORKDIR}/aos-cm-service.conf ${D}${sysconfdir}/systemd/system/aos-messageproxy.service.d/10-aos-cm-service.conf
}

# Do not install headers files
# This is temporary solution and should be removed when switching to new repo approach
do_install:append() {
    rm -rf ${D}${includedir}
}
