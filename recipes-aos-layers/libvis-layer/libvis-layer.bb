SUMMARY = "libvis layer"

AOS_PARENT_LAYER = "py-libs-layer"

require recipes-aos-layers/py-libs-layer/py-libs-layer.bb

AOS_LAYER_FEATURES += " \
    libvis \
"

AOS_LAYER_VERSION = "1"
