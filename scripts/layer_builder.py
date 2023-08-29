#!/usr/bin/env python3
""" Script for building Aos layers """
import argparse
import os
import sys

import yaml
from bitbake import call_bitbake


def read_layers_file(enabled_file):
    """Reads layers file."""
    layers = []

    for line in enabled_file:
        line = line.strip()

        if len(line) > 0 and line[0] != "#":
            if line not in layers:
                layers.append(line)

    return layers


def main():
    """Main function"""
    ret = 0
    parser = argparse.ArgumentParser(description="fota")

    parser.add_argument(
        "conf", metavar="conf.yaml", type=str, help="YAML file with configuration"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument("-l", "--layers", nargs="*", help="List of enabled layers")
    parser.add_argument(
        "-f", "--file", action="store", help="Config file with enabled layers"
    )

    args = parser.parse_args()

    with open(args.conf, "r", encoding="utf-8") as conf_file:
        conf = yaml.load(conf_file, Loader=yaml.CLoader)

    if args.layers is not None or args.file is not None:
        enabled_layers = []

        if args.layers is not None:
            enabled_layers = list(args.layers)

        if args.file is not None:
            try:
                with open(args.file, "r", encoding="utf-8") as enabled_file:
                    enabled_layers.extend(read_layers_file(enabled_file))
            except FileNotFoundError:
                print(f"File {args.file} can't be opened")
    else:
        enabled_layers = None

    layers_conf = conf["layers"]

    for layer in layers_conf["items"]:
        layer_conf = layers_conf["items"][layer]

        if enabled_layers:
            enabled = layer in enabled_layers
        else:
            enabled = layer_conf.get("enabled", True)

        bbake_conf = [
            ("AOS_BASE_IMAGE", layers_conf["base_image"]),
            ("AOS_LAYER_DEPLOY_DIR", os.path.abspath(layers_conf["output_dir"])),
        ]

        if enabled:
            ret = call_bitbake(
                conf.get("work_dir", "layers"),
                layers_conf.get("yocto_dir", "yocto"),
                layers_conf.get("build_dir", "build"),
                layer_conf["target"],
                bbake_conf,
            )

    return ret


if __name__ == "__main__":
    sys.exit(main())
