#!/usr/bin/env python3
"""Script for building AOS layers with unified metadata generation."""

import argparse
import os
import shutil
import sys

import yaml
from bitbake import call_bitbake
from metadata_builder import BundleBuilder
from moulin import rouge


def build_layer(
    layers_conf: rouge.YamlValue,
    layer_conf: rouge.YamlValue,
    layer_dir: str,
) -> int:
    """Build a single layer using bitbake into its own subdirectory."""

    if os.path.exists(layer_dir):
        shutil.rmtree(layer_dir)
    os.makedirs(layer_dir)

    bbake_conf = [
        ("AOS_BASE_IMAGE", layers_conf["base_image"].as_str),
        ("AOS_LAYER_DEPLOY_DIR", layer_dir),
    ]

    version = layer_conf.get("version", None)
    if version:
        bbake_conf.append(("AOS_LAYER_VERSION", version.as_str))

    return call_bitbake(
        layers_conf.get("work_dir", "workdir").as_str,
        layers_conf.get("yocto_dir", "yocto").as_str,
        layers_conf.get("build_dir", "build").as_str,
        layer_conf["target"].as_str,
        bbake_conf,
    )


def main():
    """Main function."""

    parser = argparse.ArgumentParser(description="AOS Layer builder")
    parser.add_argument(
        "conf", metavar="conf.yaml", type=str, help="YAML file with configuration"
    )
    args = parser.parse_args()

    with open(args.conf, "r", encoding="utf-8") as f:
        conf = rouge.YamlValue(yaml.compose(f))

    layers_conf = conf.get("layers", conf)

    builder = BundleBuilder(layers_conf, "layer")
    builder.prepare()

    ret = 0
    items = layers_conf["items"]

    for name in items.keys():
        item_conf = items[name]

        if not item_conf.get("enabled", True).as_bool:
            continue

        print(f"Building layer: {name}")

        layer_dir = os.path.join(builder._output_dir, name)
        result = build_layer(layers_conf, item_conf, layer_dir)

        if result != 0:
            print(f"Failed to build layer: {name}")

            ret = result
        else:
            builder.add_item_from_conf(name, item_conf)

    if ret != 0:
        print("Some layers failed to build")

        return ret

    builder.build()

    return 0


if __name__ == "__main__":
    sys.exit(main())
