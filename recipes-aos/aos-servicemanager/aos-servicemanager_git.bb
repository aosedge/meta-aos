DESCRIPTION = "AOS Service Manager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=86d3f3a95c324c9479bd8986968f4327"

BRANCH = "feature_unification"
SRCREV = "${AUTOREV}"

SRC_URI = "git://github.com/aosedge/aos_core_cpp.git;protocol=https;branch=${BRANCH}"

SRC_URI += " \
    file://sm.cfg \
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
    ${@bb.utils.contains("AOS_CONTAINER_RUNNER", "runc", "${VIRTUAL_RUNC}", "${AOS_CONTAINER_RUNNER}", d)} \
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

do_fetch[vardeps] += " \
    AOS_COMPONENT_RUNTIME_PREFIX \
    AOS_CONTAINER_RUNNER \
"

python do_update_config() {
    import json

    file_name = oe.path.join(d.getVar("D"), d.getVar("sysconfdir"), "aos", "sm.cfg")

    with open(file_name) as f:
        data = json.load(f)

    node_hostname = d.getVar("AOS_NODE_HOSTNAME")
    main_node_hostname = d.getVar("AOS_MAIN_NODE_HOSTNAME")

    # Update IAM servers

    data["iamProtectedServerUrl"] = node_hostname + ":8089"
    data["iamPublicServerUrl"] = node_hostname + ":8090"

    # Update CM server

    data["cmServerUrl"] = main_node_hostname + ":8093"

    # Update component prefixes and set container runner

    comp_prefix = d.getVar("AOS_COMPONENT_RUNTIME_PREFIX")
    container_runner = d.getVar("AOS_CONTAINER_RUNNER")

    for runtime in data["runtimes"]:
        if runtime["plugin"] == "container":
            runtime["type"] = container_runner

        isComponent = runtime.get("isComponent", False)

        if isComponent and not runtime["type"].startswith(comp_prefix):
            runtime["type"] = comp_prefix + runtime["type"]

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
}

do_install:append() {
    install -d ${D}${sysconfdir}/aos
    install -m 0644 ${WORKDIR}/sm.cfg ${D}${sysconfdir}/aos

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${WORKDIR}/aos-sm.service ${D}${systemd_system_unitdir}

    install -d ${D}${sysconfdir}/systemd/system/aos-sm.service.d
    install -m 0644 ${WORKDIR}/aos-dirs-service.conf ${D}${sysconfdir}/systemd/system/aos-sm.service.d/20-aos-dirs-service.conf

    install -d ${D}${sysconfdir}/systemd/system/aos.target.d
    install -m 0644 ${WORKDIR}/aos-target.conf ${D}${sysconfdir}/systemd/system/aos.target.d/${PN}.conf

    install -m 0644 ${S}/src/sm/launcher/runtimes/container/aos-service@.service ${D}${systemd_system_unitdir}
    sed -i 's/@RUNNER@/${AOS_CONTAINER_RUNNER}/g' ${D}${systemd_system_unitdir}/aos-service@.service

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
