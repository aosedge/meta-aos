# Aos uses nftables exclusively. iproute2 links libxtables only to provide
# tc's "action xt/ipt" modules (which Aos does not use); that linkage is what
# drags the whole iptables package into the image. Drop the iptables build
# dependency so tc is built without libxtables and no longer pulls iptables.
DEPENDS:remove = "iptables"

# Those xt/ipt action modules were the only shared objects under ${libdir}/tc
# (the rest are linked into the tc binary), so without them the directory is
# installed empty. Drop it so packaging does not flag it as
# installed-but-not-shipped.
do_install:append() {
    rmdir "${D}${libdir}/tc" 2>/dev/null || true
}
