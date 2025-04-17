#!/usr/bin/env python3
"""Script for building Aos layers"""
import argparse
import os
import sys

import yaml
from bitbake import call_bitbake


def main():
    """Main function"""
    ret = 0

    parser = argparse.ArgumentParser(description="Layer builder")

    parser.add_argument(
        "conf", metavar="conf.yaml", type=str, help="YAML file with configuration"
    )

    args = parser.parse_args()

    with open(args.conf, "r", encoding="utf-8") as conf_file:
        conf = yaml.load(conf_file, Loader=yaml.CLoader)

    layers_conf = conf["layers"]

    for layer in layers_conf["items"]:
        layer_conf = layers_conf["items"][layer]

        bbake_conf = [
            ("AOS_BASE_IMAGE", layers_conf["base_image"]),
            (
                "AOS_LAYER_DEPLOY_DIR",
                os.path.abspath(layers_conf.get("output_dir", "../output/layers")),
            ),
        ]

        if layer_conf.get("enabled", True):
            result = call_bitbake(
                conf.get("work_dir", "workdir"),
                layers_conf.get("yocto_dir", "yocto"),
                layers_conf.get("build_dir", "build"),
                layer_conf["target"],
                bbake_conf,
            )

            if result != 0:
                ret = result

    return ret


if __name__ == "__main__":
    sys.exit(main())
