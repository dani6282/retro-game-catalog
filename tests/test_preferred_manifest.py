#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_preferred_manifest import build_manifest, release_identity
from title_normalization import detect_language, title_key


def entry(
    entry_id: str,
    title: str,
    platform: str,
    path: str,
    *,
    source: str = "Batocera",
    collection: str | None = None,
    category: str | None = None,
) -> dict:
    return {
        "id": entry_id,
        "title": title,
        "normalizedTitle": title_key(title),
        "source": source,
        "platform": platform,
        "collection": collection or platform,
        "category": category,
        "format": "zip",
        "language": None,
        "path": path,
        "absolutePath": f"/source/{path}",
        "sizeBytes": 100,
    }


class LanguageTests(unittest.TestCase):
    def test_compact_pimiga_suffixes(self) -> None:
        self.assertEqual(detect_language("CivilizationAGADe"), "German")
        self.assertEqual(detect_language("DreamWebDe"), "German")
        self.assertEqual(detect_language("SimonTheSorcererAGAFr"), "French")
        self.assertEqual(title_key("CivilizationAGADe"), title_key("CivilizationDe"))

    def test_region_tokens(self) -> None:
        self.assertEqual(detect_language("Mining (Germany)"), "German")
        self.assertEqual(detect_language("Game (USA)"), "English")
        self.assertIsNone(detect_language("Game (Europe)"))
        self.assertEqual(detect_language("Art De La Guerre Fr"), "French")


class SelectionTests(unittest.TestCase):
    def build(self, games: list[dict]) -> dict:
        return build_manifest({"generatedAt": "fixture", "sourceRoots": {}, "games": games})

    def test_german_wins_and_platforms_remain_separate(self) -> None:
        manifest = self.build(
            [
                entry("c64-en", "Turrican (Europe)", "c64", "c64/Turrican (Europe).zip"),
                entry("c64-de", "Turrican (Germany)", "c64", "c64/Turrican (Germany).zip"),
                entry("amiga-en", "Turrican", "amiga500", "amiga500/Turrican.zip"),
            ]
        )
        self.assertEqual(manifest["summary"]["selected"], 2)
        selected = {record["groupKey"]: record for record in manifest["selected"]}
        self.assertEqual(selected["c64:turrican"]["language"], "German")
        self.assertIn("amiga:turrican", selected)

    def test_multidisk_release_is_one_selection(self) -> None:
        disk1 = entry("d1", "B.A.T. II (De)_Disk1", "amiga500", "amiga500/B.A.T. II (De)_Disk1.zip")
        disk2 = entry("d2", "B.A.T. II (De)_Disk2", "amiga500", "amiga500/B.A.T. II (De)_Disk2.zip")
        manifest = self.build([disk1, disk2])
        self.assertEqual(release_identity(disk1), release_identity(disk2))
        self.assertEqual(manifest["summary"]["selected"], 1)
        self.assertEqual(len(manifest["selected"][0]["candidate"]["assets"]), 2)
        self.assertFalse(manifest["selected"][0]["reviewRequired"])

    def test_whdload_wins_over_floppy_in_same_language(self) -> None:
        manifest = self.build(
            [
                entry("floppy", "Dune (De)", "amiga500", "amiga500/Dune (De).zip"),
                entry(
                    "whd",
                    "DuneDe",
                    "Amiga",
                    "WHDLOAD/OCS/D/DuneDe",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="OCS",
                ),
            ]
        )
        selected = manifest["selected"][0]["candidate"]
        self.assertEqual(selected["library"], "PiMiga")
        self.assertEqual(selected["collection"], "WHDLoad")

    def test_competing_amiga_editions_require_review(self) -> None:
        manifest = self.build(
            [
                entry(
                    "aga",
                    "CivilizationAGADe",
                    "Amiga",
                    "WHDLOAD/AGA/C/CivilizationAGADe",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="AGA",
                ),
                entry(
                    "ocs",
                    "CivilizationDe",
                    "Amiga",
                    "WHDLOAD/OCS/C/CivilizationDe",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="OCS",
                ),
            ]
        )
        self.assertEqual(manifest["summary"]["selected"], 1)
        self.assertEqual(manifest["summary"]["needsReview"], 1)
        self.assertIn(
            "competing-amiga-hardware-editions",
            manifest["needsReview"][0]["reviewReasons"],
        )

    def test_support_directories_are_excluded(self) -> None:
        manifest = self.build(
            [
                entry(
                    "audio",
                    "audio",
                    "Amiga",
                    "audio",
                    source="PiMiga",
                    collection="Installed",
                    category="Direct",
                )
            ]
        )
        self.assertEqual(manifest["summary"]["selected"], 0)
        self.assertEqual(manifest["summary"]["excluded"], 1)


if __name__ == "__main__":
    unittest.main()
