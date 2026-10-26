"""Discover pack targets and source directories from upstream configuration."""

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)+(?:-[A-Za-z0-9][A-Za-z0-9_-]*)?")


def _source_versions(root: Path) -> set[str]:
    projects = root / "projects"
    versions = set()
    if not projects.is_dir():
        return versions
    for directory in projects.iterdir():
        if (directory / "assets").is_dir() and VERSION_PATTERN.fullmatch(directory.name):
            versions.add(directory.name)
    assets = projects / "assets"
    if assets.is_dir():
        for mod in assets.iterdir():
            if mod.is_dir():
                versions.update(
                    path.name for path in mod.iterdir()
                    if path.is_dir() and VERSION_PATTERN.fullmatch(path.name)
                )
    return versions


def version_sort_key(version: str) -> tuple:
    base, _, loader = version.partition("-")
    return tuple(int(part) for part in re.findall(r"\d+", base)), loader, version


def _config_records(root: Path) -> dict[str, dict[str, Any]]:
    records = {}
    legacy = root / "config/packer.json"
    if legacy.is_file():
        for record in json.loads(legacy.read_text(encoding="utf-8-sig")):
            version = record.get("targetVersion")
            if isinstance(version, str) and version:
                records[version] = record

    for path in sorted((root / "config/packer").glob("*.json")):
        if path.stem == "packer-example":
            continue
        record = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(record, dict) or not isinstance(record.get("base"), dict):
            continue
        version = record["base"].get("version")
        if not isinstance(version, str) or not version:
            continue
        records[version] = record

    # A translated version can precede its upstream packer configuration.
    # Reuse the matching base version's text rules, without inventing fallbacks.
    for version in sorted(_source_versions(root), key=version_sort_key):
        if version in records:
            continue
        template = records.get(version.split("-", 1)[0])
        record = deepcopy(template) if template is not None else {
            "base": {"targetLanguages": ["zh_cn"]},
            "floating": {"exclusionPaths": ["packer-policy.json", "local-config.json", "README.md"]},
        }
        base = record.setdefault("base", dict(record))
        base["version"] = version
        base["fallbackVersions"] = []
        records[version] = record
    return records


def discover_versions(root: Path) -> list[str]:
    versions = sorted(_config_records(root), key=version_sort_key)
    if not versions:
        raise ValueError(f"No packer targets found in upstream config: {root}")
    return versions


def load_config_record(root: Path, version: str) -> dict[str, Any]:
    try:
        return _config_records(root)[version]
    except KeyError:
        raise FileNotFoundError(f"Missing packer config for version {version}: {root / 'config'}") from None


def iter_mod_directories(
    root: Path, version: str, fallback_versions: Iterable[str] = (),
) -> Iterable[tuple[str, Path]]:
    """Select the first available version per mod in either upstream layout."""
    selected = {}
    found_layout = False
    for candidate_version in dict.fromkeys((version, *fallback_versions)):
        modern = root / "projects/assets"
        legacy = root / "projects" / candidate_version / "assets"
        if modern.is_dir():
            found_layout = True
            for mod in sorted(modern.iterdir()):
                path = mod / candidate_version
                if mod.is_dir() and path.is_dir():
                    selected.setdefault(mod.name, path)
        if legacy.is_dir():
            found_layout = True
            for mod in sorted(legacy.iterdir()):
                if mod.is_dir():
                    selected.setdefault(mod.name, mod)
    if not found_layout:
        raise FileNotFoundError(f"No assets root found for version {version}: {root / 'projects'}")
    yield from sorted(selected.items())


def main(root: Path) -> None:
    versions = discover_versions(root)
    newest = versions[-1].split("-", 1)[0]
    latest = newest if newest in versions else versions[-1]
    print(f"versions={json.dumps(versions)}")
    print(f"latest={latest}")


if __name__ == "__main__":
    import sys

    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Minecraft-Mod-Language-Package"))
