DESCRIPTION = "An implementation of docker-compose with podman backend"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://LICENSE;md5=b234ee4d69f5fce4486a80fdaf4a4263"

# meta-virtualization pins 1.0.6, which runs every "up" step (image pull, create, start) strictly
# sequentially - a batch of N benchmark items takes N times as long to pull as it should. 1.6.0
# parallelizes the pull phase (asyncio.gather over one pull task per distinct image), which is the
# dominant cost for a cold multi-item deploy - confirmed by reading its prepare_images()/
# pull_images() against 1.0.6's plain sequential loop. 1.6.0 also dropped setup.py for a
# pyproject.toml-only setuptools build, hence python_setuptools_build_meta instead of the
# setuptools3 the 1.0.6 recipe uses.
inherit python_setuptools_build_meta

SRC_URI = "git://github.com/containers/podman-compose.git;branch=main;protocol=https \
           file://0001-pyproject-license-dict-form.patch \
"

SRCREV = "0f6537e9cfa38f6035ac57c1716b6d55dbaf3ca4"

S = "${WORKDIR}/git"

DEPENDS += "python3-pyyaml-native"

RDEPENDS:${PN} += "\
    python3-asyncio \
    python3-dotenv \
    python3-json \
    python3-pyyaml \
    python3-unixadmin \
"
