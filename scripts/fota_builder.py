#!/usr/bin/env python3
""" Create fota archive """
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from bitbake import call_bitbake
from moulin import rouge


class FotaError(Exception):
    """Exception raised for errors during creating FOTA archive

    Attributes:
        error code -- Error code
        message -- explanation of the error
    """

    def __init__(self, error_code, message="FOTA error"):
        self.code = error_code
        self.message = f"{message} ({self.code})"

        super().__init__(self.message)


class FotaBuilder:
    """Create fota archive class"""

    def __init__(self, conf, verbose) -> None:
        self._work_dir = conf["work_dir"].as_str
        self._components = conf["components"]
        self._verbose = verbose
        self._bundle_name = conf["target_images"][0].as_str
        self._metadata = {"formatVersion": 1, "components": []}
        self._bundle_dir = os.path.join(self._work_dir, "bundle")

    def create_bundle(self):
        """Create bundle from prepared files"""

        self._prepare_dir(os.path.dirname(self._bundle_name))

        args = ["tar", "-cf", self._bundle_name, "-C", self._bundle_dir, "."]

        self._run_cmd(args)

    def process_component(self, component, conf):
        """Process component "component" """
        metadata = self._create_component_metadata(component, conf)
        work_dir = os.path.join(self._work_dir, "components", metadata["id"])
        method = conf["method"].as_str

        if method == "raw":
            self._do_raw_component(work_dir, metadata, conf)
        elif method == "overlay":
            self._do_overlay_component(work_dir, metadata, conf)
        elif method == "custom":
            self._do_custom_component(metadata, conf)

        self._metadata["components"].append(metadata)

    def create_metadata(self):
        """Create metadata file in bundle directory"""
        metadata_file_name = os.path.join(self._bundle_dir, "metadata.json")

        with open(metadata_file_name, "w", encoding="utf-8") as metadata_file:
            json.dump(self._metadata, metadata_file, indent=4)

    def get_components(self):
        """Get dictionary with components configuration"""
        return self._components

    def prepare_bundle_dir(self):
        """Prepare empty temporary dir for bundle"""
        self._prepare_dir(self._bundle_dir)

    def _run_cmd(self, args):
        if self._verbose:
            print("Running:", " ".join(args))

        ret = subprocess.run(args, check=True)
        if ret.returncode != 0:
            raise FotaError(ret.returncode)

    def _do_copy(self, src, dst):
        if self._verbose:
            print(f"Copy from {src} to {dst}")

        args = ["cp", "-Lf", src, dst]

        self._run_cmd(args)

    def _prepare_dir(self, wdir):
        if os.path.exists(wdir):
            if os.path.isfile(wdir):
                os.remove(wdir)
            else:
                shutil.rmtree(wdir)

        os.makedirs(wdir, exist_ok=True)

    def _mkdir(self, root, new_dir):
        if len(new_dir) == 0:
            return

        dirs = Path(new_dir).parts
        path = root

        for dir_component in dirs:
            path = os.path.join(path, dir_component)

            if not os.path.exists(path):
                os.mkdir(path)

    def _update_metadata_var(self, conf, varname, metadata):
        var = conf.get(varname, None)

        if var:
            metadata[varname] = var.as_str

    def _create_component_metadata(self, component, conf):
        metadata = {
            "id": conf.get("componentType", component).as_str,
            "vendorVersion": conf["vendorVersion"].as_str,
        }
        metadata["fileName"] = conf.get(
            "fileName", f'{metadata["id"]}-{metadata["vendorVersion"]}.img'
        ).as_str

        self._update_metadata_var(conf, "requiredVersion", metadata)
        self._update_metadata_var(conf, "minVersion", metadata)
        self._update_metadata_var(conf, "maxVersion", metadata)
        self._update_metadata_var(conf, "description", metadata)
        self._update_metadata_var(conf, "annotations", metadata)
        self._update_metadata_var(conf, "downloadTTL", metadata)

        return metadata

    def _do_raw_component(self, work_dir, metadata, conf):
        """Create archive for raw component"""
        self._prepare_dir(work_dir)

        block_entry = rouge.construct_entry(conf["partition"])
        image_file = os.path.join(work_dir, "image.raw")

        with open(image_file, "wb") as file:
            file.truncate(block_entry.size())
            block_entry.write(file, 0)

        gz_image = os.path.join(self._bundle_dir, metadata["fileName"])

        os.system(f"gzip < {image_file} > {gz_image}")

    def _do_overlay_component(self, work_dir, metadata, conf):
        component = metadata["id"]
        overlay_type = conf["type"].as_str

        self._prepare_dir(work_dir)

        if self._verbose:
            print(f"Creating {overlay_type} overlay image for {component}")

        annotats = metadata.get("annotations", {})
        annotats["type"] = overlay_type
        metadata["annotations"] = annotats

        repo = conf.get(
            "ostree_repo",
            os.path.join(self._work_dir, "ostree_repo", component),
        ).as_str

        bbake_conf = [
            ("AOS_ROOTFS_IMAGE_TYPE", overlay_type),
            ("AOS_ROOTFS_IMAGE_VERSION", metadata["vendorVersion"]),
            ("AOS_ROOTFS_REF_VERSION", metadata.get("requiredVersion", "")),
            ("AOS_ROOTFS_OSTREE_REPO", os.path.abspath(repo)),
            (
                "AOS_ROOTFS_IMAGE_FILE",
                os.path.join(os.path.abspath(self._bundle_dir), metadata["fileName"]),
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

    def _do_custom_component(self, metadata, conf):
        src = conf["file"]
        self._do_copy(src, os.path.join(self._bundle_dir, metadata["fileName"]))

    def _exclude_items(self, rootfs_dir, conf):
        exclude = conf.get("exclude", None)

        if not exclude:
            return

        for item in exclude:
            value = item.as_str

            if self._verbose:
                print(f"Exclude item: {value}")

            if value[0] == os.sep:
                value = value[1:]
            os.system(f"rm -rf {os.path.join(rootfs_dir, value)}")


def main():
    """main procedure"""
    parser = argparse.ArgumentParser(description="fota")

    parser.add_argument(
        "conf", metavar="conf.yaml", type=str, help="YAML file with configuration"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    args = parser.parse_args()
    conf = yaml.compose(open(args.conf, "r", encoding="utf-8"))

    builder = FotaBuilder(rouge.YamlValue(conf), args.verbose)

    try:
        builder.prepare_bundle_dir()

        components = builder.get_components()

        for component in components.keys():  # pylint: disable=consider-using-dict-items
            print(f"Processing {component}...")

            if not components[component].get("enabled", True).as_bool:
                if args.verbose:
                    print(f"{component} skipped")

                continue

            builder.process_component(component, components[component])

        builder.create_metadata()
        builder.create_bundle()
    except FotaError as err:
        print(err)

    return 0


if __name__ == "__main__":
    sys.exit(main())
