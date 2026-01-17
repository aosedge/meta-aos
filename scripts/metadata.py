#!/usr/bin/env python3
"""Unified metadata module for AOS update items (layers and components)."""

import os
import shutil
import tarfile
from typing import List, Literal, Optional

import yaml
from moulin import rouge
from pydantic import BaseModel, Field

LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar+gzip"
COMPONENT_FULL_MEDIA_TYPE = "vnd.aos.image.component.full.v1+gzip"
COMPONENT_INC_MEDIA_TYPE = "vnd.aos.image.component.inc.v1+gzip"

ItemType = Literal["layer", "component", "service"]


class AosArchInfo(BaseModel):
    """CPU architecture information."""

    architecture: str  # amd64, arm64, arm
    variant: Optional[str] = None


class AosOsInfo(BaseModel):
    """Operating system information."""

    os: str = "linux"
    version: Optional[str] = None
    features: Optional[List[str]] = None


class AosIdentity(BaseModel):
    """AOS object identifier."""

    codename: str
    type: ItemType
    title: Optional[str] = None
    description: Optional[str] = None


class AosImage(BaseModel):
    """Image information for an update item."""

    media_type: str = Field(alias="mediaType")
    arch_info: AosArchInfo = Field(alias="archInfo")
    os_info: AosOsInfo = Field(default_factory=AosOsInfo, alias="osInfo")
    source_folder: Optional[str] = Field(default=None, alias="sourceFolder")
    path: Optional[str] = None

    class Config:
        populate_by_name = True


class AosDependencyIdentity(BaseModel):
    """Identity for dependency reference."""

    codename: str
    type: ItemType


class AosDependency(BaseModel):
    """Dependency on another AOS object."""

    identity: AosDependencyIdentity
    versions: str  # semver constraint, e.g., ">=1.0.0", "5.2.1"


class AosUpdateItem(BaseModel):
    """Single update item (layer, component, or service)."""

    identity: AosIdentity
    version: str
    images: List[AosImage]
    dependencies: Optional[List[AosDependency]] = None


class AosPublisher(BaseModel):
    """Publisher information."""

    company: Optional[str] = None
    author: Optional[str] = None


class AosUploadMetaConfig(BaseModel):
    """Root configuration for update items upload."""

    schema_version: int = Field(default=2, alias="schemaVersion")
    publisher: Optional[AosPublisher] = None
    items: List[AosUpdateItem]

    class Config:
        populate_by_name = True


def write_config_yaml(config: AosUploadMetaConfig, output_path: str) -> None:
    """Write AosUploadMetaConfig to YAML file."""

    data = config.model_dump(by_alias=True, exclude_none=True)

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(
            data, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )


class BundleBuilder:
    """Builder for creating update bundles with unified metadata."""

    def __init__(self, bundle_conf: rouge.YamlValue, item_type: ItemType) -> None:
        self._item_type = item_type
        self._conf = bundle_conf

        self._machine = bundle_conf.get("machine", "genericx86-64").as_str
        self._architecture = bundle_conf.get("architecture", "amd64").as_str
        self._os = bundle_conf.get("os", "linux").as_str
        self._output_dir = os.path.abspath(
            bundle_conf.get("output_dir", "../output").as_str
        )
        self._bundle_dir = os.path.abspath(
            bundle_conf.get("bundle_dir", "../output/bundle").as_str
        )
        self._archive_name = bundle_conf.get("archive_name", "bundle.tar.gz").as_str

        bundle_type = bundle_conf.get("type", None)
        self._is_incremental = bundle_type and bundle_type.as_str == "incremental"

        publisher_conf = bundle_conf.get("publisher", None)
        self._publisher = None
        if publisher_conf:
            company = publisher_conf.get("company", None)
            author = publisher_conf.get("author", None)
            self._publisher = AosPublisher(
                company=company.as_str if company else None,
                author=author.as_str if author else None,
            )

        self._items: List[AosUpdateItem] = []

    def prepare(self) -> None:
        """Prepare empty bundle directory."""

        if os.path.exists(self._bundle_dir):
            shutil.rmtree(self._bundle_dir)
        os.makedirs(self._bundle_dir, exist_ok=True)

    def add_item(self, item: AosUpdateItem) -> None:
        """Add update item to bundle."""

        self._items.append(item)

    def add_item_from_conf(self, name: str, item_conf: rouge.YamlValue) -> bool:
        """Create and add item from config. Returns True on success."""

        version = item_conf.get("version", "1.0.0").as_str
        codename = item_conf.get("codename", name).as_str
        os_name = item_conf.get("os", self._os).as_str
        architecture = item_conf.get("architecture", self._architecture).as_str

        archive_path = self._find_archive(item_conf)
        if not archive_path:
            print(f"Warning: Archive not found for: {name}")

            return False

        dst_filename = f"{os_name}-{architecture}.tar.gz"
        dst_subpath = f"{codename}/{dst_filename}"
        self._copy_file(archive_path, dst_subpath)

        image = self._create_image(dst_subpath, architecture, os_name)

        title = item_conf.get("title", None)
        description = item_conf.get("description", None)
        item = AosUpdateItem(
            identity=AosIdentity(
                codename=codename,
                type=self._item_type,
                title=title.as_str if title else None,
                description=description.as_str if description else None,
            ),
            version=version,
            images=[image],
            dependencies=self._create_dependencies(item_conf),
        )

        self._items.append(item)

        return True

    def _find_archive(self, item_conf: rouge.YamlValue) -> Optional[str]:
        """Find built archive in output directory."""

        target = item_conf["target"].as_str
        version = item_conf.get("version", "1.0.0").as_str

        filename = f"{target}-{self._machine}-{version}.tar.gz"
        filepath = os.path.join(self._output_dir, filename)

        if os.path.exists(filepath):
            return filepath

        if os.path.exists(self._output_dir):
            for fname in os.listdir(self._output_dir):
                if fname.startswith(f"{target}-{self._machine}-") and fname.endswith(
                    ".tar.gz"
                ):
                    return os.path.join(self._output_dir, fname)

        return None

    def _copy_file(self, src_path: str, dst_subpath: str) -> str:
        """Copy file to bundle directory."""

        dst_path = os.path.join(self._bundle_dir, dst_subpath)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copy2(src_path, dst_path)

        return dst_subpath

    def _create_image(self, path: str, architecture: str, os_name: str) -> AosImage:
        """Create AosImage based on item type."""

        if self._item_type == "layer":
            media_type = LAYER_MEDIA_TYPE
        else:
            media_type = (
                COMPONENT_INC_MEDIA_TYPE
                if self._is_incremental
                else COMPONENT_FULL_MEDIA_TYPE
            )

        return AosImage(
            mediaType=media_type,
            path=path,
            archInfo=AosArchInfo(architecture=architecture),
            osInfo=AosOsInfo(os=os_name),
        )

    def _create_dependencies(
        self, item_conf: rouge.YamlValue
    ) -> Optional[List[AosDependency]]:
        """Create dependencies list from config."""

        deps_conf = item_conf.get("dependencies", None)
        if not deps_conf:
            return None

        dependencies = []
        for dep in deps_conf:
            dependencies.append(
                AosDependency(
                    identity=AosDependencyIdentity(
                        codename=dep["codename"].as_str,
                        type=dep.get("type", "component").as_str,
                    ),
                    versions=dep["versions"].as_str,
                )
            )

        return dependencies if dependencies else None

    def create_config(self) -> None:
        """Create config.yaml in bundle directory."""

        config = AosUploadMetaConfig(
            items=self._items,
            publisher=self._publisher,
        )
        config_path = os.path.join(self._bundle_dir, "config.yaml")
        write_config_yaml(config, config_path)
        print(f"Created: {config_path}")

    def create_archive(self) -> str:
        """Create final tar.gz archive and return its path."""

        archive_path = os.path.join(self._output_dir, self._archive_name)

        if os.path.exists(archive_path):
            os.remove(archive_path)

        with tarfile.open(archive_path, "w:gz") as tar:
            for item in os.listdir(self._bundle_dir):
                item_path = os.path.join(self._bundle_dir, item)
                tar.add(item_path, arcname=item)

        print(f"Created bundle archive: {archive_path}")

        return archive_path

    def cleanup(self) -> None:
        """Remove bundle directory and source archives."""

        if os.path.exists(self._bundle_dir):
            shutil.rmtree(self._bundle_dir)
            print(f"Removed: {self._bundle_dir}")

        for fname in os.listdir(self._output_dir):
            if fname.endswith(".tar.gz") and fname != self._archive_name:
                fpath = os.path.join(self._output_dir, fname)
                os.remove(fpath)
                print(f"Removed: {fpath}")

    def build(self) -> str:
        """Build complete bundle: config.yaml + archive."""

        if not self._items:
            print("No items to bundle")

            return ""

        self.create_config()
        archive_path = self.create_archive()
        self.cleanup()

        return archive_path
