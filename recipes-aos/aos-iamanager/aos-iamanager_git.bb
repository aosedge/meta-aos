DESCRIPTION = "AOS Identity and Access Manager CPP"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "5d33a3d3d6c13bd4fb04468630f6a88c9c54e036"

SRC_URI = "git://github.com/aoscloud/aos_core_iam_cpp.git;protocol=https;branch=${BRANCH}"

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

do_fetch[vardeps] += "AOS_NODE_ID AOS_NODE_TYPE AOS_IAM_NODES AOS_IAM_HOSTNAMES"

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_iamanager.cfg")

    with open(file_name) as f:
        data = json.load(f)

    # Set node ID and node type
    node_info = {
        "NodeID": d.getVar("AOS_NODE_ID"),
        "NodeType" : d.getVar("AOS_NODE_TYPE")
    }

    data = {**node_info, **data}

    # Set alternative names for server certificates

    for cert_module in data["CertModules"]:
        if "ExtendedKeyUsage" in cert_module and "serverAuth" in cert_module["ExtendedKeyUsage"]:
            cert_module["AlternativeNames"] = [d.getVar("AOS_NODE_HOSTNAME")]

    # Add remote IAM's configuration

    node_id = d.getVar("AOS_NODE_ID")
    iam_nodes = d.getVar("AOS_IAM_NODES").split()
    iam_hostnames = d.getVar("AOS_IAM_HOSTNAMES").split()

    if len(iam_nodes) > 1 or (len(iam_nodes) == 1 and node_id not in iam_nodes):
        data["RemoteIams"] = []

        for i in range(len(iam_nodes)):
            if iam_nodes[i] == node_id:
                continue

            data["RemoteIams"].append({"NodeID": iam_nodes[i], "URL": iam_hostnames[i]+
                (":8089" if ":" not in iam_hostnames[i] else "")})

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
