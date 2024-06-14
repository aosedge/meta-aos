DESCRIPTION = "AOS Identity and Access Manager CPP"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "develop"
SRCREV = "${AUTOREV}"

SRC_URI = "git://github.com/aosedge/aos_core_iam_cpp.git;protocol=https;branch=${BRANCH}"

SRC_URI += " \
    file://aos_iamanager.cfg \
    file://aos-iamanager.service \
    file://aos-iamanager-provisioning.service \
    file://aos-target.conf \
"

DEPENDS += "poco systemd grpc grpc-native protobuf-native protobuf openssl"

OECMAKE_GENERATOR = "Unix Makefiles"
EXTRA_OECMAKE += "-DFETCHCONTENT_FULLY_DISCONNECTED=OFF"

inherit autotools pkgconfig cmake systemd

SYSTEMD_SERVICE:${PN} = "aos-iamanager.service aos-iamanager-provisioning.service"

FILES:${PN} += " \
    ${sysconfdir} \
"

RDEPENDS:${PN} += " \
    aos-rootca \
    aos-provfinish \
"

S = "${WORKDIR}/git"

do_compile[network] = "1"
do_configure[network] =  "1"

do_fetch[vardeps] += "AOS_MAIN_NODE_HOSTNAME AOS_NODE_HOSTNAME AOS_NODE_TYPE"

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_iamanager.cfg")

    with open(file_name) as f:
        data = json.load(f)

    node_info = data.get("NodeInfo", {})
    node_info["NodeType"] = d.getVar("AOS_NODE_TYPE")

    data["NodeInfo"] = node_info

    node_host_name = d.getVar("AOS_NODE_HOSTNAME")
    main_node_host_name = d.getVar("AOS_MAIN_NODE_HOSTNAME")

    # Set main IAM server URLs for secondary IAM nodes
    if node_host_name != main_node_host_name:
        data["MainIAMPublicServerURL"] = main_node_host_name+":8090"
        data["MainIAMProtectedServerURL"] = main_node_host_name+":8089"

    # Set alternative names for server certificates

    for cert_module in data["CertModules"]:
        if "ExtendedKeyUsage" in cert_module and "serverAuth" in cert_module["ExtendedKeyUsage"]:
            cert_module["AlternativeNames"] = [d.getVar("AOS_NODE_HOSTNAME")]

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
}

do_install:append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_iamanager.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-iamanager.service ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-iamanager-provisioning.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf
}

addtask update_config after do_install before do_package
