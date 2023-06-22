LICENSE = "Apache-2.0"

AOS_BASE_IMAGE ?= "aos-image"

# Require

require recipes-core/images/${AOS_BASE_IMAGE}.bb

# Inherit

inherit layer-generator
