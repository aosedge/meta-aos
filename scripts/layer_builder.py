#!/usr/bin/env python3
""" Script for building custom bitbake target """
import argparse
import os
import sys

import yaml


def call_bitbake(yocto_dir, conf):
    """Call bitbake"""
    cmd = [
        f"cd {yocto_dir}",
        f'. ./poky/oe-init-build-env {conf["build_dir"]}',
        f'bitbake {conf["target"]}',
    ]
    line = " && ".join(c for c in cmd)

    ret = os.system(f'bash -c "{line}"')

    return ret >> 8


def _read_layers_file(enabled_file):
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
                    enabled_layers.extend(_read_layers_file(enabled_file))
            except FileNotFoundError:
                print(f"File {args.file} can't be opened")
    else:
        enabled_layers = None

    layers = conf["layers"]
    yocto_dir = layers["yocto_dir"]

    for layer in layers["items"]:
        if enabled_layers:
            enabled = layer in enabled_layers
        else:
            enabled = layers["items"][layer].get("enabled", True)

        if enabled:
            ret = call_bitbake(yocto_dir, layers["items"][layer])

    return ret


if __name__ == "__main__":
    sys.exit(main())
