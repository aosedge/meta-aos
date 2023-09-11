# This class contains functions to generate uppdate bundle metadata

# Update bundle metadata

def create_dep(id, required_version, min_version=None, max_version=None):
    FIELD_ID = "id"
    FIELD_REQUIRED_VERSION = "requiredVersion"
    FIELD_MIN_VERSION = "minVersion"
    FIELD_MAX_VERSION = "maxVersion"

    if required_version and (min_version or max_version):
        raise RuntimeError(
            "{} should not be set along with {} or {}".format(FIELD_REQUIRED_VERSION, FIELD_MIN_VERSION, FIELD_MAX_VERSION))

    return {FIELD_ID: id, FIELD_REQUIRED_VERSION: required_version, FIELD_MIN_VERSION: min_version, FIELD_MAX_VERSION: max_version}


def create_component_metadata(id, file_name, vendor_version, description=None, install_dep=None, runtime_deps=None, annotations=None, download_ttl=None):
    FIELD_ID = "id"
    FIELD_FILE_NAME = "fileName"
    FIELD_VENDOR_VERSION = "vendorVersion"
    FIELD_DESCRIPTION = "description"
    FIELD_REQUIRED_VERSION = "requiredVersion"
    FIELD_MIN_VERSION = "minVersion"
    FIELD_MAX_VERSION = "maxVersion"
    FIELD_RUNTIME_DEPS = "runtimeDependencies"
    FIELD_ANNOTATIONS = "annotations"
    FIELD_DOWNLOAD_TTL = "downloadTTL"

    # check mandatory fields
    if not id or not file_name or not vendor_version:
        raise RuntimeError(
            "mandatory field ({} or {} or {}) is missing".format(FIELD_ID, FIELD_FILE_NAME, FIELD_VENDOR_VERSION))

    component = {FIELD_ID: id, FIELD_FILE_NAME: file_name,
                 FIELD_VENDOR_VERSION: vendor_version, FIELD_DESCRIPTION: description, FIELD_ANNOTATIONS: annotations,
                 FIELD_DOWNLOAD_TTL: download_ttl}

    # install dep
    if install_dep:
        if not isinstance(install_dep, dict):
            raise RuntimeError(
                "install_deps should be dictionary")

        if install_dep.get(FIELD_REQUIRED_VERSION) and (install_dep.get(FIELD_MIN_VERSION) or install_dep.get(FIELD_MAX_VERSION)):
            raise RuntimeError(
                "{} should not be set along with {} or {}".format(FIELD_REQUIRED_VERSION, FIELD_MIN_VERSION, FIELD_MAX_VERSION))

        install_deps_id = install_dep.get(FIELD_ID)

        if install_deps_id and install_deps_id != id:
            raise RuntimeError(
                "install deps {} should be equal to item {}".format(FIELD_ID, FIELD_ID))

        component[FIELD_REQUIRED_VERSION] = install_dep.get(
            FIELD_REQUIRED_VERSION)
        component[FIELD_MIN_VERSION] = install_dep.get(FIELD_MIN_VERSION)
        component[FIELD_MAX_VERSION] = install_dep.get(FIELD_MAX_VERSION)

    # runtime deps
    if runtime_deps:
        if not isinstance(runtime_deps, list):
            raise RuntimeError(
                "runtime_deps should be list")

        component[FIELD_RUNTIME_DEPS] = []

        for dep in runtime_deps:
            if not isinstance(dep, dict):
                raise RuntimeError(
                    "runtime_deps item should be dict")

            if not dep.get(FIELD_ID):
                raise RuntimeError(
                    "missing mandatory field {} in runtime deps".format(FIELD_ID))

            if dep.get(FIELD_REQUIRED_VERSION) and (dep.get(FIELD_MIN_VERSION) or dep.get(FIELD_MAX_VERSION)):
                raise RuntimeError(
                    "{} should not be set along with {} or {}".format(FIELD_REQUIRED_VERSION, FIELD_MIN_VERSION, FIELD_MAX_VERSION))

            component[FIELD_RUNTIME_DEPS].append(
                {FIELD_ID: dep.get(FIELD_ID), FIELD_REQUIRED_VERSION: dep.get(FIELD_REQUIRED_VERSION),
                 FIELD_MIN_VERSION: dep.get(FIELD_MIN_VERSION), FIELD_MAX_VERSION: dep.get(FIELD_MAX_VERSION)})

    return component

def remove_empty_elements(metadata):
    def empty(value):
        return not value or value == {} or value == []

    if not isinstance(metadata, (dict, list)):
        return metadata
    elif isinstance(metadata, list):
        return [value for value in (remove_empty_elements(value) for value in metadata) if not empty(value)]
    else:
        return {key: value for key, value in ((key, remove_empty_elements(value)) for key, value in metadata.items()) if not empty(value)}

def write_image_metadata(output_dir, components):
    import os
    import json

    FORMAT_VERSION = 1
    METADATA_FILE_NAME = "metadata.json"

    FIELD_FORMAT_VERSION = "formatVersion"
    FIELD_COMPONENTS = "components"

    # check mandatory fields
    if not components:
        raise RuntimeError(
            "mandatory field ({}) is missing".format(FIELD_COMPONENTS))

    if not isinstance(components, list):
        raise RuntimeError(
            "components should be list")

    for component in components:
        if not isinstance(component, dict):
            raise RuntimeError(
                "components item should be dict")

    metadata = {FIELD_FORMAT_VERSION: FORMAT_VERSION, FIELD_COMPONENTS: components}

    metadata = remove_empty_elements(metadata)

    with open(os.path.join(output_dir, METADATA_FILE_NAME), 'w') as outfile:
        json.dump(metadata, outfile, indent=4)

# Layer metadata

def create_layer_platform_info(arch, os, os_version, os_features):
    FIELD_ARCH = "architecture"
    FIELD_OS = "os"
    FIELD_OS_VERSION = "osVersion"
    FIELD_OS_FEATURES = "osFeatures"

    return {FIELD_ARCH : arch, FIELD_OS: os, FIELD_OS_VERSION: os_version, FIELD_OS_FEATURES: os_features}

def create_layer_annotations(layer_id, parent_layer_id=None, parent_layer_digest=None):
    FIELD_LAYER_ID = "layerId"
    FIELD_PARENT_LAYER_ID = "parrentLayerId"
    FIELD_PARENT_LAYER_DIGEST = "parrentLayerDigest"

    return {FIELD_LAYER_ID : layer_id, FIELD_PARENT_LAYER_ID: parent_layer_id, FIELD_PARENT_LAYER_DIGEST: parent_layer_digest}

def write_layer_metadata(output_dir, media_type, digest, size, platform_info=None, annotations=None):
    import os
    import json

    FIELD_MEDIATYPE = "mediaType"
    FIELD_DIGEST = "digest"
    FIELD_SIZE = "size"
    FIELD_PLATFORM = "platform"
    FIELD_ANNOTATIONS = "annotations"

    METADATA_FILE_NAME = "metadata.json"

    # check mandatory fields
    if not media_type or not digest or not size:
        raise RuntimeError(
            "mandatory field ({} or {} or {}) is missing".format(FIELD_MEDIATYPE, FIELD_DIGEST, FIELD_SIZE))

    metadata = {FIELD_MEDIATYPE: media_type, FIELD_DIGEST: digest, FIELD_SIZE: size,
        FIELD_PLATFORM: platform_info, FIELD_ANNOTATIONS: annotations}

    metadata = remove_empty_elements(metadata)

    with open(os.path.join(output_dir, METADATA_FILE_NAME), 'w') as outfile:
        json.dump(metadata, outfile, indent=4)
