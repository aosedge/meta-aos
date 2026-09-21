SUMMARY = "Generic command-timing benchmark helper"
DESCRIPTION = "Runs a given command and pushes checkpoint_event samples bracketing it ('Start \
<name>' / 'Stop <name>'), the same shape of data the AosCore/Podman/k3s benchmark deployable items \
push themselves. Does not compute or push a duration itself - a separate service calculates that \
from the Start/Stop event pair. Not tied to any one benchmark scenario or container runtime - the \
command being timed is whatever the caller passes after '--', so this can wrap \
'podman-compose start', 'kubectl apply', 'podman build', or any other shell command run on \
the unit."

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = " \
    file://time_event.py \
"

S = "${WORKDIR}"

RDEPENDS:${PN} += " \
    python3-core \
"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/time_event.py ${D}${bindir}/time_event.py
}
