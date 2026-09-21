# containerd is in the image (benchmark builds only) as the runtime binary k3s launches itself:
# this recipe of k3s has no bundled runtime, so k3s starts the containerd found in PATH as its own
# child process, with its own socket and state (/run/k3s/containerd, /var/lib/rancher/k3s). The
# standalone containerd.service isn't used by k3s or anything else here, and an enabled one would keep
# an idle daemon running during the AosCore and Podman measurements too. Keep the binary, don't
# start the service at boot.
SYSTEMD_AUTO_ENABLE:${PN} = "disable"
