SUMMARY = "kuksa client layer"

require recipes-aos-layers/aos-base-layer/aos-base-layer.inc

AOS_LAYER_FEATURES += " \
    kuksa-client \
"

AOS_LAYER_VERSION = "1.0.0"
