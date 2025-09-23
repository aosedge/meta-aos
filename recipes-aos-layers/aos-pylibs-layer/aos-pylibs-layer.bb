SUMMARY = "python libs layer"

require recipes-aos-layers/aos-base-layer/aos-base-layer.inc

AOS_LAYER_FEATURES += " \
    python3-aiohttp \
    python3-compression \
    python3-crypt \
    python3-json \
    python3-misc \
    python3-requests \
    python3-shell \
    python3-six \
    python3-socketio \
    python3-threading \
    python3-websocket-client \
    kuksa-client \
"

AOS_LAYER_VERSION = "1.0.0"
