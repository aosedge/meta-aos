DESCRIPTION = "AOS Service Manager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

BRANCH = "feature_unification"
SRCREV = "${AUTOREV}"

SRC_URI = "gitsm://github.com/aosedge/aos_core_cpp.git;protocol=https;branch=${BRANCH}"

SRC_URI += " \
    file://aos_sm.cfg \
    file://aos-sm.service \
    file://aos-target.conf \
    file://aos-dirs-service.conf \
    file://aos-cm-service.conf \
"

S = "${WORKDIR}/git"

inherit cmake pkgconfig systemd

SYSTEMD_SERVICE:${PN} = "aos-sm.service"

MIGRATION_SCRIPTS_PATH = "${base_prefix}/usr/share/aos/sm/migration"

FILES:${PN} += " \
    ${sysconfdir} \
    ${systemd_system_unitdir} \
    ${MIGRATION_SCRIPTS_PATH} \
"

DEPENDS = "grpc grpc-native poco protobuf-native systemd curl libnl"

do_configure[network] =  "1"

EXTRA_OECMAKE += " \
    -DFETCHCONTENT_FULLY_DISCONNECTED=OFF \
    -DWITH_CM=OFF \
    -DWITH_IAM=OFF \
    -DWITH_MP=OFF \
    -DWITH_SM=ON \
"
OECMAKE_GENERATOR = "Unix Makefiles"

PACKAGECONFIG ??= "openssl"

PACKAGECONFIG[openssl] = "-DWITH_OPENSSL=ON,-DWITH_OPENSSL=OFF,openssl,"
PACKAGECONFIG[mbedtls] = "-DWITH_MBEDTLS=ON,-DWITH_MBEDTLS=OFF,,"

VIRTUAL_RUNC = "${@bb.utils.contains('LAYERSERIES_CORENAMES', 'dunfell', 'virtual/runc', 'virtual-runc', d)}"

RDEPENDS:${PN} += " \
    aos-rootca \
    iptables \
    quota \
    cni \
    aos-firewall \
    aos-dnsname \
    ${@bb.utils.contains("AOS_RUNNER", "runc", "${VIRTUAL_RUNC}", "${AOS_RUNNER}", d)} \
"

RDEPENDS:${PN}:append:aos-secondary-node = " \
    packagegroup-core-nfs-client \
"

RRECOMMENDS:${PN} += " \
    kernel-module-8021q \
    kernel-module-bridge \
    kernel-module-ifb \
    kernel-module-nf-conncount \
    kernel-module-nfnetlink \
    kernel-module-overlay \
    kernel-module-veth \
    kernel-module-vxlan \
    kernel-module-xt-addrtype \
    kernel-module-xt-comment \
    kernel-module-xt-conntrack \
    kernel-module-xt-masquerade \
    kernel-module-xt-tcpudp \
    kernel-module-sch-tbf \
    kernel-module-sch-ingress \
    kernel-module-act-mirred \
"

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "aos_sm.cfg")

    with open(file_name) as f:
        data = json.load(f)

    node_hostname = d.getVar("AOS_NODE_HOSTNAME")
    main_node_hostname = d.getVar("AOS_MAIN_NODE_HOSTNAME")

    # Update IAM servers

    data["IAMProtectedServerURL"] = node_hostname+":8089"
    data["IAMPublicServerURL"] = node_hostname+":8090"

    # Update CM server

    data["CMServerURL"] = main_node_hostname+":8093"

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
}

do_install:append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/aos_sm.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-sm.service ${D}${systemd_system_unitdir}
    
    install -m 0644 ${S}/src/sm/runner/aos-service@.service ${D}${systemd_system_unitdir}
    sed -i 's/@RUNNER@/${AOS_RUNNER}/g' ${D}${systemd_system_unitdir}/aos-service@.service

    install -d ${D}${sysconfdir}/systemd/system/aos-sm.service.d
    install -m 0644 ${WORKDIR}/aos-dirs-service.conf ${D}${sysconfdir}/systemd/system/aos-sm.service.d/20-aos-dirs-service.conf

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf

    install -d ${D}${MIGRATION_SCRIPTS_PATH}
    source_migration_path="/src/sm/database/migration"
    if [ -d ${S}${source_migration_path} ]; then
        install -m 0644 ${S}${source_migration_path}/* ${D}${MIGRATION_SCRIPTS_PATH}
    fi
}

do_install:append:aos-main-node() {
    install -d ${D}${sysconfdir}/systemd/system/aos-sm.service.d
    install -m 0644 ${WORKDIR}/aos-cm-service.conf ${D}${sysconfdir}/systemd/system/aos-sm.service.d/10-aos-cm-service.conf
}

addtask update_config after do_install before do_package
