DESCRIPTION = "AOS Message Proxy"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

BRANCH = "main"
SRCREV = "9a3190834a2543e38b600c57bac31e7bf7503ff8"

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

do_fetch[vardeps] += "AOS_MAIN_NODE_HOSTNAME AOS_NODE_HOSTNAME"

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_messageproxy.cfg")

    with open(file_name) as f:
        data = json.load(f)

    iamConfig = data.get("IAMConfig", {})
    iamConfig["IAMPublicServerURL"] = d.getVar("AOS_NODE_HOSTNAME") + ":8090"
    iamConfig["IAMMainPublicServerURL"] = d.getVar("AOS_MAIN_NODE_HOSTNAME") + ":8090"
    iamConfig["IAMMainProtectedServerURL"] = d.getVar("AOS_MAIN_NODE_HOSTNAME") + ":8089"

    cmConfig = data.get("CMConfig", {})
    cmConfig["CMServerURL"] = d.getVar("AOS_MAIN_NODE_HOSTNAME") + ":8093"

    data["IAMConfig"] = iamConfig
    data["CMConfig"] = cmConfig

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
}

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

addtask update_config after do_install before do_package
