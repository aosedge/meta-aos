#!/usr/bin/env python3
""" Script for building custom bitbake target """
import argparse
import os
import sys

import yaml


def call_bitbake(work_dir, yocto_dir, build_dir, layer_conf, common_conf):
    """Call bitbake."""
    target = layer_conf["target"]

    print(f"\nCreating {target} layer...")

    # Create config file

    conf_file = os.path.abspath(os.path.join(work_dir, f"{target}.conf"))

    create_conf_file(conf_file, layer_conf.get("conf", None), common_conf)

    cmd = [
        f"cd {yocto_dir}",
        f". ./poky/oe-init-build-env {build_dir}",
        f"bitbake {target} --postread {conf_file}",
    ]
    line = " && ".join(c for c in cmd)

    ret = os.system(f'bash -c "{line}"')

    return ret >> 8


def create_conf_file(conf_file, layer_conf, common_conf):
    """Creates yocto conf file for layer."""
    conf = []

    conf += common_conf if common_conf else []
    conf += layer_conf if layer_conf else []

    with open(conf_file, "w+", encoding="utf8") as file:
        for var in conf:
            file.write(f'{var[0]} = "{var[1]}"\n')


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

    layers = conf["layers"]
    work_dir = conf.get("work_dir", "layers")
    yocto_dir = layers.get("yocto_dir", "yocto")
    build_dir = layers.get("build_dir", "build")
    common_conf = layers.get("conf", None)

    for layer in layers["items"]:
        if enabled_layers:
            enabled = layer in enabled_layers
        else:
            enabled = layers["items"][layer].get("enabled", True)

        if enabled:
            ret = call_bitbake(
                work_dir, yocto_dir, build_dir, layers["items"][layer], common_conf
            )

    return ret


if __name__ == "__main__":
    sys.exit(main())
