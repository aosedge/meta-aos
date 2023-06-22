SUMMARY = "vim layer"

require recipes-aos-layers/base-layer/base-layer.inc

AOS_LAYER_FEATURES += " \
    vim \
"

AOS_LAYER_WHITEOUTS += " \
    /var/cache/fontconfig \
    /usr/share/fontconfig/* \
    /usr/share/applications/gvim.desktop \
    /usr/share/applications/vim.desktop \
"

AOS_LAYER_VERSION = "1"
