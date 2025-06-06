SUMMARY = "A shim around Click that renders help output nicely using Rich."
HOMEPAGE = "https://github.com/ewels/rich-click"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=5372b77c3720be60b7eff9a9a5c0000d"

PYPI_PACKAGE = "rich_click"

SRC_URI[sha256sum] = "0f49471f04439269d0e66a6f43120f52d11d594869a2a0be600cfb12eb0616b9"

inherit pypi python_setuptools_build_meta

RDEPENDS:${PN} += " \
    python3-click \
    python3-rich \
"

BBCLASSEXTEND += "native nativesdk"
