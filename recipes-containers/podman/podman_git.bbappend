# meta-virtualization defaults podman's network backend to CNI. Netavark (aardvark-dns built in) is
# used instead: it enables DNS on user networks without a separate CNI plugin. Set here, not
# globally - only podman reads this variable.
VIRTUAL-RUNTIME_container_networking = "netavark"

# That variable only injects one package - "netavark" - into podman's own RDEPENDS. aardvark-dns
# (netavark's DNS resolver) isn't pulled in by it on its own; add it explicitly.
RDEPENDS:${PN} += "${@bb.utils.contains('VIRTUAL-RUNTIME_container_networking', 'netavark', 'aardvark-dns', '', d)}"

# Netavark's port-mapping DNAT chain uses "-m addrtype --dst-type LOCAL"; without this module every
# container start fails with "Extension addrtype revision 0 not supported". meta-virtualization's
# recipe already lists it, but only as a plain RRECOMMENDS - state it here explicitly for the
# netavark backend this layer selects.
RRECOMMENDS:${PN} += "kernel-module-xt-addrtype"
