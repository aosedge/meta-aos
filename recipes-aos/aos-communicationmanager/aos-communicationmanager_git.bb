DESCRIPTION = "AOS Communication Manager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

BRANCH = "feature_unification"
SRCREV = "${AUTOREV}"

SRC_URI = "gitsm://github.com/aosedge/aos_core_cpp.git;protocol=https;branch=${BRANCH}"

SRC_URI += " \
    file://aos_cm.cfg \
    file://aos-cm.service \
    file://aos-target.conf \
    file://aos-dirs-service.conf \
"

S = "${WORKDIR}/git"

inherit cmake pkgconfig systemd

SYSTEMD_SERVICE:${PN} = "aos-cm.service"

MIGRATION_SCRIPTS_PATH = "${base_prefix}/usr/share/aos/cm/migration"

FILES:${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
    ${MIGRATION_SCRIPTS_PATH} \
"

DEPENDS = "grpc grpc-native poco protobuf-native systemd curl libnl"

do_configure[network] =  "1"

EXTRA_OECMAKE += " \
    -DFETCHCONTENT_FULLY_DISCONNECTED=OFF \
    -DWITH_CM=ON \
    -DWITH_IAM=OFF \
    -DWITH_MP=OFF \
    -DWITH_SM=OFF \
"
OECMAKE_GENERATOR = "Unix Makefiles"

PACKAGECONFIG ??= "openssl"

PACKAGECONFIG[openssl] = "-DWITH_OPENSSL=ON,-DWITH_OPENSSL=OFF,openssl,"
PACKAGECONFIG[mbedtls] = "-DWITH_MBEDTLS=ON,-DWITH_MBEDTLS=OFF,,"

RDEPENDS:${PN} += " \
    aos-rootca \
    nfs-exports \
"

RRECOMMENDS:${PN} += " \
    kernel-module-quota-v1 \
    kernel-module-quota-v2 \
    kernel-module-quota-tree \
"

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_cm.cfg")

    with open(file_name) as f:
        data = json.load(f)

    node_hostname = d.getVar("AOS_NODE_HOSTNAME")
 
    # Update IAM servers
    
    data["IAMProtectedServerURL"]= node_hostname+":8089"
    data["IAMPublicServerURL"] = node_hostname+":8090"

    # Update DNS IP

    dns_ip = d.getVar("AOS_DNS_IP")
    if dns_ip:
        data["DNSIP"] = dns_ip

    main_node_hostname = d.getVar("AOS_MAIN_NODE_HOSTNAME")

    # Update SM controller
    sm_controller = data["SMController"]
    sm_controller["FileServerURL"] = main_node_hostname+":8094"

    # Update CM controller
    um_controller = data["UMController"]
    um_controller["FileServerURL"] = main_node_hostname+":8092"

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
}

do_install:append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_cm.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-cm.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf

    install -d ${D}${sysconfdir}/systemd/system/aos-cm.service.d
    install -m 0644 ${WORKDIR}/aos-dirs-service.conf ${D}${sysconfdir}/systemd/system/aos-cm.service.d/10-aos-dirs-service.conf

    install -d ${D}${MIGRATION_SCRIPTS_PATH}
    source_migration_path="/src/cm/database/migration"
    if [ -d ${S}${source_migration_path} ]; then
        install -m 0644 ${S}${source_migration_path}/* ${D}${MIGRATION_SCRIPTS_PATH}
    fi
}

addtask update_config after do_install before do_package
