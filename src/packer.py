from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

OUTPUT_DIR = Path("DictPacker")
DEFAULT_UPSTREAM_ROOT = Path("./Minecraft-Mod-Language-Package")
UPSTREAM_ROOT_ENV = "I18N_DICT_UPSTREAM_ROOT"
LANG_LIKE_SUFFIXES = {".lang", ".local", ".hl"}
TEXT_SUFFIXES = {".txt", ".json", ".md", ".lang", ".local", ".hl"}
VALID_NAMESPACE_RE = re.compile(r"^[a-z0-9_.-]+$")


@dataclass(frozen=True)
class SourceMeta:
    modid: str
    curseforge: str


@dataclass(frozen=True)
class BaseConfig:
    version: str
    target_languages: tuple[str, ...]
    exclusion_mods: tuple[str, ...]
    exclusion_namespaces: tuple[str, ...]


@dataclass(frozen=True)
class FloatingConfig:
    inclusion_domains: tuple[str, ...] = ()
    exclusion_domains: tuple[str, ...] = ()
    exclusion_paths: tuple[str, ...] = ()
    inclusion_paths: tuple[str, ...] = ()
    character_replacement: dict[str, str] = field(default_factory=dict)
    destination_replacement: dict[str, str] = field(default_factory=dict)

    def merge(self, other: "FloatingConfig | None") -> "FloatingConfig":
        if other is None:
            return self
        return FloatingConfig(
            inclusion_domains=tuple(dict.fromkeys(self.inclusion_domains + other.inclusion_domains)),
            exclusion_domains=tuple(dict.fromkeys(self.exclusion_domains + other.exclusion_domains)),
            exclusion_paths=tuple(dict.fromkeys(self.exclusion_paths + other.exclusion_paths)),
            inclusion_paths=tuple(dict.fromkeys(self.inclusion_paths + other.inclusion_paths)),
            character_replacement={**self.character_replacement, **other.character_replacement},
            destination_replacement={**self.destination_replacement, **other.destination_replacement},
        )


@dataclass(frozen=True)
class Config:
    base: BaseConfig
    floating: FloatingConfig

    def modify(self, floating: FloatingConfig | None) -> "Config":
        if floating is None:
            return self
        return Config(base=self.base, floating=self.floating.merge(floating))


@dataclass(frozen=True)
class ApplyOptions:
    modify_only: bool = False
    append: bool = False


@dataclass(frozen=True)
class Policy:
    type: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceProvider:
    destination: str
    meta: SourceMeta

    def apply_to(self, base: "ResourceProvider | None", options: ApplyOptions) -> "ResourceProvider":
        return self if base is None else base

    def replace_content(self, search_pattern: str, replacement: str) -> "ResourceProvider":
        return self

    def replace_destination(self, search_pattern: str, replacement: str) -> "ResourceProvider":
        raise NotImplementedError

    def rebind_meta(self, meta: SourceMeta) -> "ResourceProvider":
        raise NotImplementedError


@dataclass(frozen=True)
class MappingProvider(ResourceProvider):
    mapping_format: str
    mapping: dict[str, Any]
    provenance: dict[str, SourceMeta]

    def apply_to(self, base: ResourceProvider | None, options: ApplyOptions) -> "ResourceProvider":
        if base is None:
            return self
        if not isinstance(base, MappingProvider) or base.mapping_format != self.mapping_format:
            raise TypeError(f"Cannot merge mapping provider with {type(base).__name__}")

        merged = deepcopy(base.mapping)
        provenance = dict(base.provenance)
        for key, value in self.mapping.items():
            if options.modify_only:
                if key in merged:
                    merged[key] = deepcopy(value)
                    provenance[key] = self.provenance.get(key, self.meta)
            elif key not in merged:
                merged[key] = deepcopy(value)
                provenance[key] = self.provenance.get(key, self.meta)
        return MappingProvider(
            destination=self.destination,
            meta=base.meta,
            mapping_format=self.mapping_format,
            mapping=merged,
            provenance=provenance,
        )

    def replace_content(self, search_pattern: str, replacement: str) -> "MappingProvider":
        return MappingProvider(
            destination=self.destination,
            meta=self.meta,
            mapping_format=self.mapping_format,
            mapping={
                key: replace_string_leaves(value, search_pattern, replacement)
                for key, value in self.mapping.items()
            },
            provenance=dict(self.provenance),
        )

    def replace_destination(self, search_pattern: str, replacement: str) -> "MappingProvider":
        return MappingProvider(
            destination=normalize_path(re.sub(search_pattern, replacement, self.destination, flags=re.S)),
            meta=self.meta,
            mapping_format=self.mapping_format,
            mapping=deepcopy(self.mapping),
            provenance=dict(self.provenance),
        )

    def rebind_meta(self, meta: SourceMeta) -> "MappingProvider":
        return MappingProvider(
            destination=self.destination,
            meta=meta,
            mapping_format=self.mapping_format,
            mapping=deepcopy(self.mapping),
            provenance={key: meta for key in self.mapping},
        )


@dataclass(frozen=True)
class TextProvider(ResourceProvider):
    content: str

    def apply_to(self, base: ResourceProvider | None, options: ApplyOptions) -> "ResourceProvider":
        if base is None:
            return self
        if not isinstance(base, TextProvider):
            raise TypeError(f"Cannot merge text provider with {type(base).__name__}")
        if not options.append:
            return base
        return TextProvider(
            destination=self.destination,
            meta=base.meta,
            content=f"{base.content}\n{self.content}",
        )

    def replace_content(self, search_pattern: str, replacement: str) -> "TextProvider":
        return TextProvider(
            destination=self.destination,
            meta=self.meta,
            content=re.sub(search_pattern, replacement, self.content, flags=re.S),
        )

    def replace_destination(self, search_pattern: str, replacement: str) -> "TextProvider":
        return TextProvider(
            destination=normalize_path(re.sub(search_pattern, replacement, self.destination, flags=re.S)),
            meta=self.meta,
            content=self.content,
        )

    def rebind_meta(self, meta: SourceMeta) -> "TextProvider":
        return TextProvider(destination=self.destination, meta=meta, content=self.content)


@dataclass(frozen=True)
class RawProvider(ResourceProvider):
    source_file: Path

    def replace_destination(self, search_pattern: str, replacement: str) -> "RawProvider":
        return RawProvider(
            destination=normalize_path(re.sub(search_pattern, replacement, self.destination, flags=re.S)),
            meta=self.meta,
            source_file=self.source_file,
        )

    def rebind_meta(self, meta: SourceMeta) -> "RawProvider":
        return RawProvider(destination=self.destination, meta=meta, source_file=self.source_file)


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def resolve_upstream_root(cli_root: str | None = None) -> Path:
    root = cli_root or os.getenv(UPSTREAM_ROOT_ENV)
    return Path(root) if root else DEFAULT_UPSTREAM_ROOT


def validate_namespace(namespace: str) -> bool:
    if not VALID_NAMESPACE_RE.match(namespace):
        raise ValueError(f"Invalid namespace name: {namespace}")
    return True


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _coerce_str_tuple(value: Any) -> tuple[str, ...]:
    return tuple(item for item in (value or ()) if isinstance(item, str))


def _parse_config_record(raw_version: dict[str, Any], fallback_version: str) -> Config:
    base_section = raw_version.get("base", raw_version)
    floating_section = raw_version.get("floating", {})

    base_version = (
        base_section.get("version")
        or raw_version.get("targetVersion")
        or fallback_version
    )
    base = BaseConfig(
        version=str(base_version),
        target_languages=_coerce_str_tuple(base_section.get("targetLanguages", base_section.get("unTargetLang", ()))),
        exclusion_mods=_coerce_str_tuple(
            base_section.get("exclusionMods", base_section.get("modNameBlackList", ()))
        ),
        exclusion_namespaces=_coerce_str_tuple(
            base_section.get("exclusionNamespaces", base_section.get("noProcessNamespace", ()))
        ),
    )
    floating = FloatingConfig(
        inclusion_domains=_coerce_str_tuple(
            floating_section.get(
                "inclusionDomains",
                floating_section.get(
                    "inclusionDomainWhiteList",
                    base_section.get("inclusionDomains", base_section.get("inclusionDomainWhiteList", ())),
                ),
            )
        ),
        exclusion_domains=_coerce_str_tuple(
            floating_section.get(
                "exclusionDomains",
                floating_section.get(
                    "domainBlackList",
                    base_section.get("exclusionDomains", base_section.get("domainBlackList", ())),
                ),
            )
        ),
        exclusion_paths=_coerce_str_tuple(
            floating_section.get("exclusionPaths", base_section.get("exclusionPaths", ()))
        ),
        inclusion_paths=_coerce_str_tuple(
            floating_section.get("inclusionPaths", base_section.get("inclusionPaths", ()))
        ),
        character_replacement=dict(floating_section.get("characterReplacement", {})),
        destination_replacement=dict(floating_section.get("destinationReplacement", base_section.get("destinationReplacement", {}))),
    )
    return Config(base=base, floating=floating)


def strip_json_comments(text: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False
    single_comment = False
    multi_comment = False
    index = 0
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""

        if single_comment:
            if char == "\n":
                single_comment = False
                result.append(char)
            index += 1
            continue

        if multi_comment:
            if char == "*" and nxt == "/":
                multi_comment = False
                index += 2
            else:
                if char == "\n":
                    result.append(char)
                index += 1
            continue

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == "/" and nxt == "/":
            single_comment = True
            index += 2
            continue
        if char == "/" and nxt == "*":
            multi_comment = True
            index += 2
            continue
        if char == '"':
            in_string = True
        result.append(char)
        index += 1

    return "".join(result)


def remove_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def load_relaxed_json(path: Path) -> Any:
    text = read_text(path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = remove_trailing_commas(strip_json_comments(text))
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pairs = re.findall(r'"[^"]+"\s*:\s*"[^"]+"', cleaned, flags=re.MULTILINE)
            if not pairs:
                raise
            ret: dict[str, str] = {}
            for pair in pairs:
                key, value = re.findall(r'"[^"]+"', pair, flags=re.MULTILINE)
                ret[key[1:-1]] = value[1:-1]
            return ret


def parse_lang_content(content: str) -> dict[str, str]:
    result: dict[str, str] = {}
    is_in_comment = False
    is_parse_escape = False
    is_line_continuation = False
    pending_key = ""
    pending_value = ""

    for raw_line in content.splitlines():
        line = raw_line

        if is_line_continuation:
            stripped = line.lstrip()
            if stripped.endswith("\\"):
                pending_value += stripped[:-1]
            else:
                pending_value += stripped
                result.setdefault(pending_key, pending_value)
                is_line_continuation = False
            continue

        if not is_parse_escape and line == "#PARSE_ESCAPES":
            is_parse_escape = True
            continue

        if is_in_comment:
            if line.strip().endswith("*/"):
                is_in_comment = False
            continue

        if line.startswith("//") or line.startswith("#") or line.startswith("<"):
            continue

        if line.startswith("/*"):
            is_in_comment = True
            continue

        if not line.strip():
            continue

        if line in {"{", "}"}:
            continue

        split_position = line.find("=")
        if split_position == -1:
            continue

        key = line[:split_position]
        value = line[split_position + 1:] if split_position + 1 < len(line) else ""
        if is_parse_escape and value.endswith("\\"):
            is_line_continuation = True
            pending_key = key
            pending_value = value[:-1]
        else:
            result.setdefault(key, value)

    return result


def replace_string_leaves(value: Any, search_pattern: str, replacement: str) -> Any:
    if isinstance(value, str):
        return re.sub(search_pattern, replacement, value, flags=re.S)
    if isinstance(value, list):
        return [replace_string_leaves(item, search_pattern, replacement) for item in value]
    if isinstance(value, dict):
        return {key: replace_string_leaves(item, search_pattern, replacement) for key, item in value.items()}
    return value


def load_config(upstream_root: Path, version: str) -> Config:
    legacy_path = upstream_root / "config" / "packer" / f"{version}.json"
    if legacy_path.exists():
        return _parse_config_record(json.loads(read_text(legacy_path)), version)

    packed_config_path = upstream_root / "config" / "packer.json"
    raw = json.loads(read_text(packed_config_path))
    if not isinstance(raw, list):
        raise ValueError("Invalid config format: expected a list in config/packer.json")

    matched_version = next((entry for entry in raw if entry.get("targetVersion") == version), None)
    if matched_version is None:
        base_version = version.split("-", 1)[0]
        if base_version != version:
            matched_version = next((entry for entry in raw if entry.get("targetVersion") == base_version), None)
    if matched_version is None:
        raise KeyError(f"No packer config for version {version} in config/packer.json")

    return _parse_config_record(matched_version, version)


def load_local_config(namespace_dir: Path) -> FloatingConfig | None:
    path = namespace_dir / "local-config.json"
    if not path.exists():
        return None
    raw = json.loads(read_text(path))
    return FloatingConfig(
        inclusion_domains=tuple(raw.get("inclusionDomains", [])),
        exclusion_domains=tuple(raw.get("exclusionDomains", [])),
        exclusion_paths=tuple(raw.get("exclusionPaths", [])),
        inclusion_paths=tuple(raw.get("inclusionPaths", [])),
        character_replacement=dict(raw.get("characterReplacement", {})),
        destination_replacement=dict(raw.get("destinationReplacement", {})),
    )


def load_policies(namespace_dir: Path) -> list[Policy]:
    path = namespace_dir / "packer-policy.json"
    if not path.exists():
        return [Policy(type="direct")]
    raw = json.loads(read_text(path))
    return [Policy(type=item["type"], parameters={k: v for k, v in item.items() if k != "type"}) for item in raw]


def get_apply_options(parameters: dict[str, Any]) -> ApplyOptions:
    return ApplyOptions(
        modify_only=bool(parameters.get("modifyOnly", False)),
        append=bool(parameters.get("append", False)),
    )


def is_domain_force_included(location: str, config: Config) -> bool:
    return any(location.startswith(f"{domain}/") for domain in config.floating.inclusion_domains)


def is_domain_force_excluded(location: str, config: Config) -> bool:
    return any(location.startswith(f"{domain}/") for domain in config.floating.exclusion_domains)


def is_in_target_locale(location: str, locale: str) -> bool:
    return locale.lower() in location.lower()


def is_path_force_excluded(location: str, config: Config) -> bool:
    return location in config.floating.exclusion_paths


def is_path_force_included(location: str, config: Config) -> bool:
    return location in config.floating.inclusion_paths


def resolve_repo_path(upstream_root: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else upstream_root / path


def resolve_locale_specific_path(upstream_root: Path, path_value: str, locale: str) -> Path | None:
    original = resolve_repo_path(upstream_root, path_value)
    if original.exists():
        if locale.lower() in original.name.lower() or locale.lower() in original.as_posix().lower():
            return original
        if any(tag in original.as_posix().lower() for tag in ("zh_cn", "en_us")):
            localized = Path(re.sub(r"(?i)zh_cn|en_us", locale, original.as_posix()))
            return localized if localized.exists() else None
        return original

    localized = Path(re.sub(r"(?i)zh_cn|en_us", locale, original.as_posix()))
    return localized if localized.exists() else None


def create_mapping_provider(destination: str, mapping_format: str, mapping: dict[str, Any], meta: SourceMeta) -> MappingProvider:
    return MappingProvider(
        destination=normalize_path(destination),
        meta=meta,
        mapping_format=mapping_format,
        mapping=mapping,
        provenance={key: meta for key in mapping},
    )


def create_provider_from_file(file_path: Path, destination: str, meta: SourceMeta) -> ResourceProvider:
    extension = file_path.suffix.lower()
    if file_path.parent.name == "lang":
        if extension == ".json":
            data = load_relaxed_json(file_path)
            if not isinstance(data, dict):
                data = {}
            return create_mapping_provider(destination, "json", data, meta)
        if extension == ".lang":
            return create_mapping_provider(destination, "lang", parse_lang_content(read_text(file_path)), meta)

    if extension in TEXT_SUFFIXES:
        return TextProvider(destination=normalize_path(destination), meta=meta, content=read_text(file_path))

    return RawProvider(destination=normalize_path(destination), meta=meta, source_file=file_path)


def enumerate_providers(
    namespace_dir: Path,
    config: Config,
    locale: str,
    meta: SourceMeta,
    upstream_root: Path,
) -> list[ResourceProvider]:
    grouped: dict[str, ResourceProvider] = {}
    for provider, options in enumerate_raw_providers(namespace_dir, config, locale, meta, upstream_root):
        existing = grouped.get(provider.destination)
        grouped[provider.destination] = provider.apply_to(existing, options)

    providers = list(grouped.values())
    for pattern, replacement in config.floating.character_replacement.items():
        providers = [provider.replace_content(pattern, replacement) for provider in providers]
    for pattern, replacement in config.floating.destination_replacement.items():
        providers = [provider.replace_destination(pattern, replacement) for provider in providers]
    return providers


def enumerate_raw_providers(
    namespace_dir: Path,
    config: Config,
    locale: str,
    meta: SourceMeta,
    upstream_root: Path,
) -> Iterable[tuple[ResourceProvider, ApplyOptions]]:
    for policy in load_policies(namespace_dir):
        yield from evaluate_policy(namespace_dir, config, locale, meta, upstream_root, policy)


def evaluate_policy(
    namespace_dir: Path,
    config: Config,
    locale: str,
    meta: SourceMeta,
    upstream_root: Path,
    policy: Policy,
) -> Iterable[tuple[ResourceProvider, ApplyOptions]]:
    policy_type = policy.type.lower()
    if policy_type == "direct":
        yield from from_current_directory(namespace_dir, config, locale, meta)
        return
    if policy_type == "indirect":
        yield from from_specified_directory(namespace_dir, config, locale, meta, upstream_root, policy.parameters)
        return
    if policy_type == "composition":
        yield from from_composition(namespace_dir, meta, upstream_root, locale, policy.parameters)
        return
    if policy_type == "singleton":
        yield from from_singleton(namespace_dir, meta, upstream_root, locale, policy.parameters)
        return
    raise ValueError(f"Unexpected policy type {policy.type!r} at {namespace_dir}")


def from_current_directory(
    namespace_dir: Path,
    config: Config,
    locale: str,
    meta: SourceMeta,
) -> Iterable[tuple[ResourceProvider, ApplyOptions]]:
    local_config = config.modify(load_local_config(namespace_dir))

    for candidate in sorted(namespace_dir.rglob("*")):
        if not candidate.is_file():
            continue
        relative_path = normalize_path(candidate.relative_to(namespace_dir).as_posix())
        destination = normalize_path(f"assets/{namespace_dir.name}/{relative_path}")
        if is_path_force_excluded(relative_path, local_config):
            continue
        if not (
            is_path_force_included(relative_path, local_config)
            or is_domain_force_included(relative_path, local_config)
            or (is_in_target_locale(destination, locale) and not is_domain_force_excluded(relative_path, local_config))
        ):
            continue
        yield create_provider_from_file(candidate, destination, meta), ApplyOptions()


def from_specified_directory(
    namespace_dir: Path,
    config: Config,
    locale: str,
    meta: SourceMeta,
    upstream_root: Path,
    parameters: dict[str, Any],
) -> Iterable[tuple[ResourceProvider, ApplyOptions]]:
    redirect_dir = resolve_repo_path(upstream_root, parameters["source"])
    namespace_name = namespace_dir.name
    options = get_apply_options(parameters)
    for provider, _ in enumerate_raw_providers(redirect_dir, config, locale, meta, upstream_root):
        yield provider.replace_destination(r"(?<=^assets/)[^/]*(?=/)", namespace_name), options


def composition_parameter_sets(parameters: list[dict[str, str]]) -> Iterable[tuple[tuple[str, ...], tuple[str, ...]]]:
    sets: list[tuple[tuple[str, ...], tuple[str, ...]]] = [(tuple(), tuple())]
    for group in parameters:
        next_sets: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
        for keys, values in sets:
            for key, value in group.items():
                next_sets.append((keys + (key,), values + (value,)))
        sets = next_sets
    return sets


def build_composition_mapping(source_path: Path) -> tuple[str, dict[str, str]]:
    raw = json.loads(read_text(source_path))
    mapping: dict[str, str] = {}
    for entry in raw["entries"]:
        templates = entry["templates"]
        parameter_sets = composition_parameter_sets(entry["parameters"])
        for keys, values in parameter_sets:
            for template_key, template_value in templates.items():
                formatted_key = template_key.format(*keys)
                if formatted_key in mapping:
                    continue
                mapping[formatted_key] = template_value.format(*values)
    return raw["target"], mapping


def from_composition(
    namespace_dir: Path,
    meta: SourceMeta,
    upstream_root: Path,
    locale: str,
    parameters: dict[str, Any],
) -> Iterable[tuple[ResourceProvider, ApplyOptions]]:
    source_path = resolve_locale_specific_path(upstream_root, parameters["source"], locale)
    if source_path is None:
        return
    destination, mapping = build_composition_mapping(source_path)
    mapping_format = parameters.get("destType", "json")
    yield create_mapping_provider(destination, mapping_format, mapping, meta), get_apply_options(parameters)


def from_singleton(
    namespace_dir: Path,
    meta: SourceMeta,
    upstream_root: Path,
    locale: str,
    parameters: dict[str, Any],
) -> Iterable[tuple[ResourceProvider, ApplyOptions]]:
    source_path = resolve_locale_specific_path(upstream_root, parameters["source"], locale)
    if source_path is None:
        return
    destination = normalize_path(f"assets/{namespace_dir.name}/{parameters['relativePath']}")
    yield create_provider_from_file(source_path, destination, meta), get_apply_options(parameters)


def materialize_locale(version: str, upstream_root: Path, locale: str) -> dict[str, ResourceProvider]:
    config = load_config(upstream_root, version)
    result: dict[str, ResourceProvider] = {}

    legacy_assets_dir = upstream_root / "projects" / version / "assets"
    if legacy_assets_dir.is_dir():
        mod_version_pairs = ((mod_dir, mod_dir) for mod_dir in sorted(legacy_assets_dir.iterdir(), key=lambda item: item.name))
    else:
        assets_root = upstream_root / "projects" / "assets"
        if not assets_root.is_dir():
            raise FileNotFoundError(f"No assets root found for version {version}")
        mod_version_pairs = (
            (mod_dir, mod_dir / version)
            for mod_dir in sorted(assets_root.iterdir(), key=lambda item: item.name)
            if mod_dir.is_dir()
            and (mod_dir / version).is_dir()
        )

    for mod_dir, namespace_root in mod_version_pairs:
        if not mod_dir.is_dir():
            continue
        if mod_dir.name in config.base.exclusion_mods:
            continue
        curseforge = "Unknown" if mod_dir.name == "1UNKNOWN" else mod_dir.name
        for namespace_dir in sorted(namespace_root.iterdir(), key=lambda item: item.name):
            if not namespace_dir.is_dir():
                continue
            if namespace_dir.name in config.base.exclusion_namespaces:
                continue
            validate_namespace(namespace_dir.name)
            meta = SourceMeta(modid=namespace_dir.name, curseforge=curseforge)
            providers = enumerate_providers(namespace_dir, config, locale, meta, upstream_root)
            for provider in providers:
                existing = result.get(provider.destination)
                result[provider.destination] = provider.apply_to(existing, ApplyOptions())
    return result


def join_path(base: str, segment: str) -> str:
    return segment if not base else f"{base}.{segment}"


def pair_node_leaves(origin: Any, trans: Any, base_path: str) -> list[tuple[str, str, str]]:
    if isinstance(origin, str) and isinstance(trans, str):
        return [(base_path, origin, trans)]

    pairs: list[tuple[str, str, str]] = []
    if isinstance(origin, dict) and isinstance(trans, dict):
        for key in sorted(set(origin) & set(trans)):
            pairs.extend(pair_node_leaves(origin[key], trans[key], join_path(base_path, str(key))))
        return pairs
    if isinstance(origin, list) and isinstance(trans, list):
        for index, (origin_item, trans_item) in enumerate(zip(origin, trans)):
            next_path = f"{base_path}[{index}]"
            pairs.extend(pair_node_leaves(origin_item, trans_item, next_path))
    return pairs


def build_entry(
    *,
    origin_name: str,
    trans_name: str,
    key: str,
    version: str,
    meta: SourceMeta,
) -> dict[str, str]:
    return {
        "origin_name": origin_name,
        "trans_name": trans_name,
        "modid": meta.modid,
        "key": key,
        "version": version,
        "curseforge": meta.curseforge,
    }


def extract_from_mapping_pair(
    destination: str,
    origin_provider: MappingProvider,
    trans_provider: MappingProvider,
    version: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for top_key in sorted(set(origin_provider.mapping) & set(trans_provider.mapping)):
        origin_value = origin_provider.mapping[top_key]
        trans_value = trans_provider.mapping[top_key]
        meta = trans_provider.provenance.get(top_key, trans_provider.meta)
        for path, origin_name, trans_name in pair_node_leaves(origin_value, trans_value, top_key):
            dict_key = top_key if path == top_key and isinstance(origin_value, str) and isinstance(trans_value, str) else f"{destination}#{path}"
            rows.append(
                build_entry(
                    origin_name=origin_name,
                    trans_name=trans_name,
                    key=dict_key,
                    version=version,
                    meta=meta,
                )
            )
    return rows


def parse_text_provider_content(provider: TextProvider) -> tuple[str, Any] | None:
    suffix = Path(provider.destination).suffix.lower()
    if suffix == ".json":
        try:
            return "json", json.loads(remove_trailing_commas(strip_json_comments(provider.content)))
        except json.JSONDecodeError:
            return "json", load_relaxed_json_from_text(provider.content)
    if suffix in LANG_LIKE_SUFFIXES:
        mapping = parse_lang_content(provider.content)
        if suffix in {".local", ".hl"}:
            mapping = {key.strip(): value.strip() for key, value in mapping.items()}
        return "lang-like", mapping
    if suffix in {".txt", ".md"}:
        lines = [line.strip() for line in provider.content.splitlines() if line.strip()]
        return "lines", lines
    return None


def load_relaxed_json_from_text(text: str) -> Any:
    cleaned = remove_trailing_commas(strip_json_comments(text.lstrip("\ufeff")))
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pairs = re.findall(r'"[^"]+"\s*:\s*"[^"]+"', cleaned, flags=re.MULTILINE)
        ret: dict[str, str] = {}
        for pair in pairs:
            key, value = re.findall(r'"[^"]+"', pair, flags=re.MULTILINE)
            ret[key[1:-1]] = value[1:-1]
        return ret


def extract_from_text_pair(
    destination: str,
    origin_provider: TextProvider,
    trans_provider: TextProvider,
    version: str,
) -> list[dict[str, str]]:
    origin_parsed = parse_text_provider_content(origin_provider)
    trans_parsed = parse_text_provider_content(trans_provider)
    if origin_parsed is None or trans_parsed is None or origin_parsed[0] != trans_parsed[0]:
        return []

    kind, origin_value = origin_parsed
    _, trans_value = trans_parsed
    rows: list[dict[str, str]] = []
    meta = trans_provider.meta

    if kind in {"json", "lang-like"}:
        for path, origin_name, trans_name in pair_node_leaves(origin_value, trans_value, ""):
            if not path:
                continue
            rows.append(
                build_entry(
                    origin_name=origin_name,
                    trans_name=trans_name,
                    key=f"{destination}#{path}",
                    version=version,
                    meta=meta,
                )
            )
        return rows

    if kind == "lines":
        for index, (origin_name, trans_name) in enumerate(zip(origin_value, trans_value)):
            rows.append(
                build_entry(
                    origin_name=origin_name,
                    trans_name=trans_name,
                    key=f"{destination}#line[{index}]",
                    version=version,
                    meta=meta,
                )
            )
    return rows


def extract_entries_from_pair(
    destination: str,
    origin_provider: ResourceProvider,
    trans_provider: ResourceProvider,
    version: str,
) -> list[dict[str, str]]:
    if isinstance(origin_provider, MappingProvider) and isinstance(trans_provider, MappingProvider):
        return extract_from_mapping_pair(destination, origin_provider, trans_provider, version)
    if isinstance(origin_provider, TextProvider) and isinstance(trans_provider, TextProvider):
        return extract_from_text_pair(destination, origin_provider, trans_provider, version)
    return []


def build_entries_for_version(version: str, upstream_root: Path) -> list[dict[str, str]]:
    origin_providers = {
        canonicalize_locale_destination(destination): provider
        for destination, provider in materialize_locale(version, upstream_root, "en_us").items()
    }
    trans_providers = {
        canonicalize_locale_destination(destination): provider
        for destination, provider in materialize_locale(version, upstream_root, "zh_cn").items()
    }

    rows: list[dict[str, str]] = []
    for destination in sorted(set(origin_providers) & set(trans_providers)):
        origin_provider = origin_providers[destination]
        trans_provider = trans_providers[destination]
        rows.extend(extract_entries_from_pair(trans_provider.destination, origin_provider, trans_provider, version))
    return rows


def canonicalize_locale_destination(destination: str) -> str:
    return re.sub(r"(?i)en_us|zh_cn", "{locale}", destination)


def save_entries(version: str, rows: list[dict[str, str]]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / f"Dict-{version}.json"
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=4), encoding="utf-8")


def main(version: str, upstream_root: Path) -> None:
    print("程序初始化")
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"开始处理{version}")
    rows = build_entries_for_version(version, upstream_root)
    print(f"{version}已处理{len(rows)}条")
    save_entries(version, rows)
    print(f"已生成Dict-{version}.json")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("用法：python src/packer.py <version> [upstream_root]")

    version_arg = sys.argv[1]
    upstream_root_arg = sys.argv[2] if len(sys.argv) > 2 else None
    main(version_arg, resolve_upstream_root(upstream_root_arg))
