FILESEXTRAPATHS:prepend:aos-main-node := "${THISDIR}/files/main:"
FILESEXTRAPATHS:prepend:aos-secondary-node := "${THISDIR}/files/secondary:"

DESCRIPTION = "AOS Identity and Access Manager CPP"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

BRANCH = "feature_unification"
SRCREV = "${AUTOREV}"

SRC_URI = "gitsm://github.com/aosedge/aos_core_cpp.git;protocol=https;branch=${BRANCH}"

SRC_URI += " \
    file://aos_iam.cfg \
    file://aos-iam.service \
    file://aos-iam-prov.service \
    file://aos-target.conf \
    file://aos-dirs-service.conf \
"

DEPENDS += "poco systemd grpc grpc-native protobuf-native protobuf openssl curl libnl"

EXTRA_OECMAKE += " \
    -DFETCHCONTENT_FULLY_DISCONNECTED=OFF \
    -DWITH_CM=OFF \
    -DWITH_IAM=ON \
    -DWITH_MP=OFF \
    -DWITH_SM=OFF \
"
OECMAKE_GENERATOR = "Unix Makefiles"

PACKAGECONFIG ??= "openssl"

PACKAGECONFIG[openssl] = "-DWITH_OPENSSL=ON,-DWITH_OPENSSL=OFF,openssl,"
PACKAGECONFIG[mbedtls] = "-DWITH_MBEDTLS=ON,-DWITH_MBEDTLS=OFF,,"

inherit autotools pkgconfig cmake systemd

SYSTEMD_SERVICE:${PN} = "aos-iam.service aos-iam-prov.service"

MIGRATION_SCRIPTS_PATH = "${base_prefix}/usr/share/aos/iam/migration"

FILES:${PN} += " \
    ${sysconfdir} \
    ${MIGRATION_SCRIPTS_PATH} \
"

RDEPENDS:${PN} += " \
    aos-rootca \
    aos-provfinish \
"

S = "${WORKDIR}/git"

do_compile[network] = "1"
do_configure[network] =  "1"

do_fetch[vardeps] += "AOS_MAIN_NODE AOS_MAIN_NODE_HOSTNAME AOS_NODE_HOSTNAME AOS_NODE_TYPE"

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_iam.cfg")

    with open(file_name) as f:
        data = json.load(f)

    node_info = data.get("NodeInfo", {})
    node_info["NodeType"] = d.getVar("AOS_NODE_TYPE")

    # Set Node Attributes
    node_attributes = node_info.get("Attrs", {})

    node_info["Attrs"] = node_attributes

    data["NodeInfo"] = node_info

    main_node_host_name = d.getVar("AOS_MAIN_NODE_HOSTNAME")

    # Set main IAM server URLs for secondary IAM nodes
    if not d.getVar("AOS_MAIN_NODE") or d.getVar("AOS_MAIN_NODE") == "0":
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
    install -m 0644 ${WORKDIR}/aos_iam.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-iam.service ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-iam-prov.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/systemd/system/aos-iam-prov.service.d
    install -m 0644 ${WORKDIR}/aos-dirs-service.conf ${D}${sysconfdir}/systemd/system/aos-iam-prov.service.d/20-aos-dirs-service.conf

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf

    install -d ${D}${MIGRATION_SCRIPTS_PATH}
    source_migration_path="/src/iam/database/migration"
    if [ -d ${S}${source_migration_path} ]; then
        install -m 0644 ${S}${source_migration_path}/* ${D}${MIGRATION_SCRIPTS_PATH}
    fi
}

addtask update_config after do_install before do_package
