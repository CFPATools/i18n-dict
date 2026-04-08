import json
import tempfile
import unittest
from pathlib import Path

from src.packer import (
    SourceMeta,
    build_entries_for_version,
    enumerate_providers,
    load_config,
    parse_lang_content,
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class PackerTests(unittest.TestCase):
    def make_upstream_root(self, version: str) -> Path:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        config = {
            "base": {
                "version": version,
                "targetLanguages": ["zh_cn"],
                "exclusionMods": [],
                "exclusionNamespaces": [],
            },
            "floating": {
                "inclusionDomains": [],
                "exclusionDomains": [],
                "exclusionPaths": ["packer-policy.json", "local-config.json", "README.md"],
                "inclusionPaths": [],
                "characterReplacement": {},
                "destinationReplacement": {},
            },
        }
        write(root / "config" / "packer" / f"{version}.json", json.dumps(config, ensure_ascii=False, indent=2))
        return root

    def test_parse_lang_content_supports_parse_escapes_and_comments(self) -> None:
        content = "\n".join(
            [
                "#PARSE_ESCAPES",
                "// comment",
                "/* block",
                "comment */",
                "plain.key=Plain",
                "message.key=\\",
                "  First line\\",
                "  Second line",
                "{",
                "}",
            ]
        )

        result = parse_lang_content(content)

        self.assertEqual(result["plain.key"], "Plain")
        self.assertEqual(result["message.key"], "First lineSecond line")

    def test_enumerate_providers_honors_local_config_paths_and_domains(self) -> None:
        version = "test-local"
        root = self.make_upstream_root(version)
        namespace_dir = root / "projects" / version / "assets" / "mod-a" / "ns"
        write(
            namespace_dir / "local-config.json",
            json.dumps(
                {
                    "inclusionDomains": ["manual"],
                    "exclusionDomains": [],
                    "exclusionPaths": ["lang/zh_cn.json"],
                    "inclusionPaths": ["notes/shared.txt"],
                    "characterReplacement": {},
                    "destinationReplacement": {},
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        write(namespace_dir / "lang" / "zh_cn.json", json.dumps({"skip": "跳过"}, ensure_ascii=False, indent=2))
        write(namespace_dir / "notes" / "shared.txt", "Shared text")
        write(namespace_dir / "manual" / "readme.md", "Manual text")

        config = load_config(root, version)
        providers = enumerate_providers(namespace_dir, config, "zh_cn", SourceMeta("ns", "mod-a"), root)
        destinations = {provider.destination for provider in providers}

        self.assertNotIn("assets/ns/lang/zh_cn.json", destinations)
        self.assertIn("assets/ns/notes/shared.txt", destinations)
        self.assertIn("assets/ns/manual/readme.md", destinations)

    def test_build_entries_for_version_supports_policies_and_complex_resources(self) -> None:
        version = "test-build"
        root = self.make_upstream_root(version)

        ns_dir = root / "projects" / version / "assets" / "mod-a" / "ns"
        write(
            ns_dir / "lang" / "en_us.json",
            json.dumps(
                {
                    "plain.key": "Plain EN",
                    "skip.key": "Skip EN",
                    "nested.key": ["Nested EN", 7],
                    "flag": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        write(
            ns_dir / "lang" / "zh_cn.json",
            json.dumps(
                {
                    "plain.key": "普通中文",
                    "skip.key": "跳过中文",
                    "nested.key": ["嵌套中文", 7],
                    "flag": False,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        write(
            ns_dir / "guide" / "en_us.json",
            json.dumps({"pages": [{"title": "Guide EN", "body": "Body EN"}]}, ensure_ascii=False, indent=2),
        )
        write(
            ns_dir / "guide" / "zh_cn.json",
            json.dumps({"pages": [{"title": "指南", "body": "正文"}]}, ensure_ascii=False, indent=2),
        )
        write(ns_dir / "fmlocals" / "en_us.local", "label.one = Label EN\n")
        write(ns_dir / "fmlocals" / "zh_cn.local", "label.one = 标签\n")

        source_dir = root / "projects" / version / "assets" / "source-mod" / "sourcens"
        write(
            source_dir / "lang" / "en_us.json",
            json.dumps({"shared.change": "Indirect EN", "shared.extra": "Extra EN"}, ensure_ascii=False, indent=2),
        )
        write(
            source_dir / "lang" / "zh_cn.json",
            json.dumps({"shared.change": "间接修改", "shared.extra": "额外中文"}, ensure_ascii=False, indent=2),
        )

        target_dir = root / "projects" / version / "assets" / "target-mod" / "targetns"
        write(
            target_dir / "packer-policy.json",
            json.dumps(
                [
                    {
                        "type": "singleton",
                        "source": f"projects/{version}/assets/target-mod/targetns/lang/zh_cn-base-fix.json",
                        "relativePath": "lang/zh_cn.json",
                    },
                    {"type": "direct"},
                    {
                        "type": "indirect",
                        "source": f"projects/{version}/assets/source-mod/sourcens",
                        "modifyOnly": True,
                    },
                    {
                        "type": "composition",
                        "destType": "json",
                        "source": f"projects/{version}/assets/target-mod/targetns/lang/zh_cn-composition.json",
                    },
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )
        write(
            target_dir / "lang" / "en_us.json",
            json.dumps(
                {
                    "shared.keep": "Keep EN",
                    "shared.change": "Base Change EN",
                    "plain": "Base Plain EN",
                    "comp.stone": "Stone",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        write(
            target_dir / "lang" / "zh_cn.json",
            json.dumps(
                {
                    "shared.keep": "保留原文",
                    "shared.change": "基础修改",
                    "plain": "基础普通",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        write(
            target_dir / "lang" / "zh_cn-base-fix.json",
            json.dumps({"shared.keep": "保留修正"}, ensure_ascii=False, indent=2),
        )
        write(
            target_dir / "lang" / "zh_cn-composition.json",
            json.dumps(
                {
                    "target": "assets/targetns/lang/zh_cn.json",
                    "entries": [
                        {
                            "templates": {"comp.{0}": "{0}中文"},
                            "parameters": [{"stone": "Stone"}],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        rows = build_entries_for_version(version, root)
        lookup = {(row["key"], row["origin_name"], row["trans_name"]) for row in rows}

        self.assertIn(("plain.key", "Plain EN", "普通中文"), lookup)
        self.assertIn(("assets/ns/lang/zh_cn.json#nested.key[0]", "Nested EN", "嵌套中文"), lookup)
        self.assertIn(("assets/ns/guide/zh_cn.json#pages[0].title", "Guide EN", "指南"), lookup)
        self.assertIn(("assets/ns/fmlocals/zh_cn.local#label.one", "Label EN", "标签"), lookup)
        self.assertIn(("shared.keep", "Keep EN", "保留修正"), lookup)
        self.assertIn(("shared.change", "Indirect EN", "间接修改"), lookup)
        self.assertTrue(all(row["modid"] != "targetns" for row in rows if row["key"] == "shared.extra"))
        self.assertIn(("comp.stone", "Stone", "Stone中文"), lookup)


if __name__ == "__main__":
    unittest.main()
