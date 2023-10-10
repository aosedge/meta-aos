SUMMARY = "libvis layer"

AOS_PARENT_LAYER = "aos-pylibs-layer"

require recipes-aos-layers/aos-pylibs-layer/aos-pylibs-layer.bb

AOS_LAYER_FEATURES += " \
    libvis \
"

AOS_LAYER_VERSION = "1.0.0"
