#!/usr/bin/env python3
"""Script for building AOS layers with unified metadata generation."""

import argparse
import os
import shutil
import sys
from typing import Dict, List, Optional

import yaml
from bitbake import call_bitbake
from metadata_builder import BundleBuilder
from moulin import rouge


def resolve_parent_target(
    name: str,
    item_conf: rouge.YamlValue,
    items: rouge.YamlValue,
) -> Optional[str]:
    """Return parent layer bitbake target based on item's dependency, or None."""

    dep_conf = item_conf.get("dependency", None)
    if not dep_conf:
        return None

    parent_name = dep_conf["item"].as_str

    if parent_name not in items.keys():
        raise ValueError(
            f"Layer '{name}' depends on unknown item '{parent_name}'"
        )

    return items[parent_name]["target"].as_str


def order_items(items: rouge.YamlValue) -> List[str]:
    """Topologically sort items so every parent is built before its children."""

    graph: Dict[str, Optional[str]] = {}
    for name in items.keys():
        item_conf = items[name]
        dep_conf = item_conf.get("dependency", None)
        parent = dep_conf["item"].as_str if dep_conf else None

        if parent is not None and parent not in items.keys():
            raise ValueError(
                f"Layer '{name}' depends on unknown item '{parent}'"
            )

        graph[name] = parent

    ordered: List[str] = []
    visiting: set = set()
    visited: set = set()

    def visit(node: str) -> None:
        if node in visited:
            return

        if node in visiting:
            raise ValueError(
                f"Cyclic layer dependency detected involving '{node}'"
            )

        visiting.add(node)
        parent = graph[node]

        if parent is not None:
            visit(parent)

        visiting.remove(node)
        visited.add(node)
        ordered.append(node)

    for name in graph:
        visit(name)

    return ordered


def build_layer(
    layers_conf: rouge.YamlValue,
    layer_conf: rouge.YamlValue,
    layer_dir: str,
    parent_target: Optional[str] = None,
) -> int:
    """Build a single layer using bitbake into its own subdirectory."""

    if os.path.exists(layer_dir):
        shutil.rmtree(layer_dir)
    os.makedirs(layer_dir)

    bbake_conf = [
        ("AOS_BASE_IMAGE", layers_conf["base_image"].as_str),
        ("AOS_LAYER_DEPLOY_DIR", layer_dir),
    ]

    if parent_target:
        # Scope to this recipe only; otherwise the parent layer (also
        # parsed in the same bitbake invocation) would inherit the same
        # AOS_PARENT_LAYER and create a self-dependency loop.
        target = layer_conf["target"].as_str
        bbake_conf.append((f"AOS_PARENT_LAYER:pn-{target}", parent_target))

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
    build_order = order_items(items)

    for name in build_order:
        item_conf = items[name]

        if not item_conf.get("enabled", True).as_bool:
            continue

        parent_target = resolve_parent_target(name, item_conf, items)

        print(f"Building layer: {name}")

        layer_dir = os.path.join(builder._output_dir, name)
        result = build_layer(layers_conf, item_conf, layer_dir, parent_target)

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
