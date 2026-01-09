#!/usr/bin/env python3
"""Script for building AOS components with unified metadata generation."""

import argparse
import os
import shutil
import subprocess
import sys

import yaml
from bitbake import call_bitbake
from metadata import (
    COMPONENT_FULL_MEDIA_TYPE,
    COMPONENT_INC_MEDIA_TYPE,
    AosArchInfo,
    AosDependency,
    AosDependencyIdentity,
    AosIdentity,
    AosImage,
    AosOsInfo,
    AosUpdateItem,
    BundleBuilder,
)
from moulin import rouge


class FotaError(Exception):
    """Exception raised for errors during creating FOTA archive."""

    def __init__(self, error_code, message="FOTA error"):
        self.code = error_code
        self.message = f"{message} ({self.code})"
        super().__init__(self.message)


class ComponentBuilder:
    """Builder for individual AOS components."""

    def __init__(self, conf: rouge.YamlValue, bundle_dir: str) -> None:
        self._conf = conf
        self._work_dir = conf["work_dir"].as_str
        self._bundle_dir = bundle_dir

    def build_component(self, name: str, comp_conf: rouge.YamlValue) -> str:
        """Build component and return path to the built file in bundle_dir."""
        method = comp_conf["method"].as_str
        comp_type = comp_conf.get("componentType", name).as_str
        version = comp_conf["version"].as_str

        filename = comp_conf.get("fileName", f"{comp_type}-{version}.img").as_str

        work_dir = os.path.join(self._work_dir, "components", comp_type)

        if method == "raw":
            self._do_raw_component(work_dir, filename, comp_conf)
        elif method == "overlay":
            self._do_overlay_component(
                work_dir, filename, comp_type, version, comp_conf
            )
        elif method == "custom":
            self._do_custom_component(filename, comp_conf)

        return filename

    def _prepare_dir(self, wdir: str) -> None:
        if os.path.exists(wdir):
            if os.path.isfile(wdir):
                os.remove(wdir)
            else:
                shutil.rmtree(wdir)

        os.makedirs(wdir, exist_ok=True)

    def _run_cmd(self, args: list) -> None:
        print("Running:", " ".join(args))

        ret = subprocess.run(args, check=True)
        if ret.returncode != 0:
            raise FotaError(ret.returncode)

    def _do_copy(self, src: str, dst: str) -> None:
        print(f"Copy from {src} to {dst}")
        args = ["cp", "-Lf", src, dst]
        self._run_cmd(args)

    def _do_raw_component(
        self, work_dir: str, filename: str, conf: rouge.YamlValue
    ) -> None:
        """Create archive for raw component."""

        self._prepare_dir(work_dir)

        block_entry = rouge.construct_entry(conf["partition"])
        image_file = os.path.join(work_dir, "image.raw")

        with open(image_file, "wb") as file:
            file.truncate(block_entry.size())
            block_entry.write(file, 0)

        gz_image = os.path.join(self._bundle_dir, filename)
        os.system(f"gzip < {image_file} > {gz_image}")

    def _do_overlay_component(
        self,
        work_dir: str,
        filename: str,
        comp_type: str,
        version: str,
        conf: rouge.YamlValue,
    ) -> None:
        """Create overlay component via bitbake."""

        overlay_type = conf["type"].as_str
        self._prepare_dir(work_dir)

        print(f"Creating {overlay_type} overlay image for {comp_type}")

        repo = conf.get(
            "ostree_repo",
            os.path.join(self._work_dir, "ostree_repo", comp_type),
        ).as_str

        required_version = conf.get("requiredVersion", "").as_str

        bbake_conf = [
            ("AOS_ROOTFS_IMAGE_TYPE", overlay_type),
            ("AOS_ROOTFS_IMAGE_VERSION", version),
            ("AOS_ROOTFS_REF_VERSION", required_version),
            ("AOS_ROOTFS_OSTREE_REPO", os.path.abspath(repo)),
            (
                "AOS_ROOTFS_IMAGE_FILE",
                os.path.join(os.path.abspath(self._bundle_dir), filename),
            ),
        ]

        exclude_items = conf.get("exclude", None)
        if exclude_items:
            bbake_conf.append(
                (
                    "AOS_ROOTFS_EXCLUDE_ITEMS",
                    " ".join([item.as_str for item in exclude_items]),
                )
            )

        ret = call_bitbake(
            work_dir,
            conf.get("yocto_dir", "yocto").as_str,
            conf.get("build_dir", "build").as_str,
            "aos-rootfs",
            bbake_conf,
            do_clean=True,
        )

        if ret != 0:
            raise FotaError(ret)

    def _do_custom_component(self, filename: str, conf: rouge.YamlValue) -> None:
        """Copy custom component file."""

        src = conf["file"].as_str
        self._do_copy(src, os.path.join(self._bundle_dir, filename))


def create_update_item(
    name: str,
    comp_conf: rouge.YamlValue,
    filename: str,
    architecture: str,
    os_name: str,
    is_incremental: bool,
) -> AosUpdateItem:
    """Create AosUpdateItem from component config."""

    comp_type = comp_conf.get("componentType", name).as_str
    version = comp_conf["version"].as_str

    media_type = (
        COMPONENT_INC_MEDIA_TYPE if is_incremental else COMPONENT_FULL_MEDIA_TYPE
    )

    image = AosImage(
        mediaType=media_type,
        path=filename,
        archInfo=AosArchInfo(architecture=architecture),
        osInfo=AosOsInfo(os=os_name),
    )

    dependencies = None
    runtime_deps = comp_conf.get("dependencies", [])
    if runtime_deps:
        dependencies = []
        for dep in runtime_deps:
            if isinstance(dep, rouge.YamlValue):
                dep_codename = dep["codename"].as_str
                dep_type = dep.get("type", "component").as_str
                dep_versions = dep["versions"].as_str
            else:
                dep_codename = dep["codename"]
                dep_type = dep.get("type", "component")
                dep_versions = dep["versions"]

            dependencies.append(
                AosDependency(
                    identity=AosDependencyIdentity(
                        codename=dep_codename,
                        type=dep_type,
                    ),
                    versions=dep_versions,
                )
            )

    title = None
    description = None
    if comp_conf.get("title", None):
        title = comp_conf["title"].as_str
    if comp_conf.get("description", None):
        description = comp_conf["description"].as_str

    return AosUpdateItem(
        identity=AosIdentity(
            codename=comp_type,
            type="component",
            title=title,
            description=description,
        ),
        version=version,
        images=[image],
        dependencies=dependencies if dependencies else None,
    )


def main():
    """Main function."""

    parser = argparse.ArgumentParser(description="AOS Component builder")
    parser.add_argument(
        "conf", metavar="conf.yaml", type=str, help="YAML file with configuration"
    )
    args = parser.parse_args()

    with open(args.conf, "r", encoding="utf-8") as f:
        conf = rouge.YamlValue(yaml.compose(f))

    components_conf = conf.get("components", conf)

    bundle_conf = components_conf.get("bundle", None)
    if not bundle_conf:
        print("Error: 'bundle' section not found in config")
        return 1

    bundle_builder = BundleBuilder(bundle_conf, "component")
    bundle_builder.prepare()

    comp_builder = ComponentBuilder(components_conf, bundle_builder._bundle_dir)

    items = components_conf.get("items", components_conf.get("components", {}))
    ret = 0

    for name in items.keys():
        comp_conf = items[name]

        if not comp_conf.get("enabled", True).as_bool:
            print(f"Skipping disabled component: {name}")
            continue

        print(f"Building component: {name}")

        try:
            filename = comp_builder.build_component(name, comp_conf)

            item = create_update_item(
                name,
                comp_conf,
                filename,
                bundle_builder._architecture,
                bundle_builder._os,
                bundle_builder._is_incremental,
            )
            bundle_builder.add_item(item)

        except FotaError as err:
            print(f"Failed to build component {name}: {err}")
            ret = 1

    if ret != 0:
        print("Some components failed to build")

        return ret

    bundle_builder.build()

    return 0


if __name__ == "__main__":
    sys.exit(main())
