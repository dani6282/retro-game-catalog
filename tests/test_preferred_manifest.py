#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_preferred_manifest import audit_manifest
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
    has_launchable_files: bool | None = None,
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
        "fileCount": 1,
        "hasLaunchableFiles": has_launchable_files,
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

    def test_compact_memory_suffix_preserves_title_number(self) -> None:
        self.assertEqual(title_key("Lemmings21MB"), "lemmings2")
        self.assertEqual(title_key("Lemmings 21 MB"), "lemmings2")
        self.assertEqual(title_key("ChaosEngine21MB"), "chaosengine2")
        self.assertEqual(title_key("Chaos Engine 21 MB"), "chaosengine2")
        self.assertEqual(title_key("MortalKombat21MB"), "mortalkombat2")
        self.assertEqual(title_key("Uridium22MB"), "uridium2")
        self.assertEqual(title_key("K2401MB"), "k240")
        self.assertEqual(title_key("Paradroid901MB"), "paradroid90")
        self.assertEqual(title_key("SensibleSoccer92931MB"), "sensiblesoccer9293")
        self.assertEqual(title_key("WormsCD321MB"), "worms")
        self.assertEqual(title_key("WormsDCAGA12MB"), "wormsdcaga")
        self.assertEqual(title_key("Intact15MB"), "intact")


class SelectionTests(unittest.TestCase):
    def build(self, games: list[dict], overrides: dict | None = None) -> dict:
        return build_manifest(
            {"generatedAt": "fixture", "sourceRoots": {}, "games": games},
            overrides,
        )

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

    def test_described_media_disks_remain_one_release(self) -> None:
        games = [
            entry("d1", "221B Baker Street (USA) (Disk 1)", "c64", "c64/221B Disk 1.zip"),
            entry(
                "d2",
                "221B Baker Street (USA) (Disk 2) (Case Disk 1)",
                "c64",
                "c64/221B Disk 2.zip",
            ),
            entry(
                "d3",
                "221B Baker Street (USA) (Disk 3) (Case Disk 2)",
                "c64",
                "c64/221B Disk 3.zip",
            ),
        ]
        manifest = self.build(games)
        self.assertEqual(manifest["summary"]["selected"], 1)
        self.assertEqual(len(manifest["selected"][0]["candidate"]["assets"]), 3)

    def test_official_complete_c64_set_wins_obvious_tie(self) -> None:
        manifest = self.build(
            [
                entry("plain", "Another World", "c64", "c64/Another World.zip"),
                entry(
                    "eu1",
                    "Another World (Europe) (Disk 1 Side A)",
                    "c64",
                    "c64/Another World (Europe) (Disk 1 Side A).zip",
                ),
                entry(
                    "eu2",
                    "Another World (Europe) (Disk 1 Side B)",
                    "c64",
                    "c64/Another World (Europe) (Disk 1 Side B).zip",
                ),
            ]
        )
        selected = manifest["selected"][0]
        self.assertEqual(len(selected["candidate"]["assets"]), 2)
        self.assertFalse(selected["reviewRequired"])

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
        disposition = manifest["needsReview"][0]["reviewDisposition"]
        self.assertFalse(disposition["phase1Blocking"])
        self.assertEqual(
            disposition["actions"][0]["queue"],
            "amiga-edition-launch-validation",
        )

    def test_explicit_aga_wins_within_aga_category(self) -> None:
        manifest = self.build(
            [
                entry(
                    "base",
                    "Body Blows",
                    "Amiga",
                    "WHDLOAD/AGA/B/BodyBlows",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="AGA",
                ),
                entry(
                    "aga",
                    "Body Blows AGA",
                    "Amiga",
                    "WHDLOAD/AGA/B/BodyBlowsAGA",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="AGA",
                ),
            ]
        )
        selected = manifest["selected"][0]
        self.assertEqual(selected["candidate"]["assets"][0]["id"], "aga")
        self.assertNotIn("equal-priority-candidates", selected["reviewReasons"])

    def test_complete_ocs_package_wins_over_aga_artwork_stub(self) -> None:
        manifest = self.build(
            [
                entry(
                    "aga-stub",
                    "1000 Miglia",
                    "Amiga",
                    "WHDLOAD/AGA/0-9/1000Miglia",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="AGA",
                    has_launchable_files=False,
                ),
                entry(
                    "ocs-game",
                    "1000 Miglia",
                    "Amiga",
                    "WHDLOAD/OCS/0-9/1000Miglia",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="OCS",
                    has_launchable_files=True,
                ),
            ]
        )
        selected = manifest["selected"][0]
        self.assertEqual(selected["candidate"]["assets"][0]["id"], "ocs-game")
        self.assertNotIn("competing-amiga-hardware-editions", selected["reviewReasons"])

    def test_same_release_in_multiple_hardware_folders_is_not_a_conflict(self) -> None:
        manifest = self.build(
            [
                entry(
                    "aga",
                    "Putty Squad AGA",
                    "Amiga",
                    "WHDLOAD/AGA/P/PuttySquadAGA",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="AGA",
                    has_launchable_files=True,
                ),
                entry(
                    "ocs-folder",
                    "Putty Squad AGA",
                    "Amiga",
                    "WHDLOAD/OCS/P/PuttySquadAGA",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="OCS",
                    has_launchable_files=True,
                ),
            ]
        )
        selected = manifest["selected"][0]
        self.assertEqual(selected["candidate"]["assets"][0]["id"], "aga")
        self.assertNotIn("competing-amiga-hardware-editions", selected["reviewReasons"])

    def test_manual_override_selects_and_resolves_hardware_choice(self) -> None:
        games = [
            entry(
                "aga",
                "Example AGA",
                "Amiga",
                "WHDLOAD/AGA/E/ExampleAGA",
                source="PiMiga",
                collection="WHDLoad",
                category="AGA",
                has_launchable_files=True,
            ),
            entry(
                "ocs",
                "Example",
                "Amiga",
                "WHDLOAD/OCS/E/Example",
                source="PiMiga",
                collection="WHDLoad",
                category="OCS",
                has_launchable_files=True,
            ),
        ]
        overrides = {
            "amiga:example": {
                "selector": {"releaseIdentity": "example", "category": "OCS"},
                "resolves": ["competing-amiga-hardware-editions"],
                "rationale": "Fixture chooses the OCS release.",
                "evidence": ["https://example.invalid/review"],
            }
        }

        manifest = self.build(games, overrides)

        selected = manifest["selected"][0]
        self.assertEqual(selected["candidate"]["assets"][0]["id"], "ocs")
        self.assertFalse(selected["reviewRequired"])
        self.assertEqual(selected["manualOverride"], overrides["amiga:example"])
        self.assertEqual(manifest["rejected"][0]["reason"], "manual-override")

    def test_stale_manual_override_fails_loudly(self) -> None:
        games = [entry("one", "Example", "Amiga", "amiga500/Example.zip")]
        overrides = {
            "amiga:example": {
                "selector": {"releaseIdentity": "missing"},
                "resolves": [],
            }
        }

        with self.assertRaisesRegex(ValueError, "matched 0 candidates"):
            self.build(games, overrides)

    def test_pal_release_wins_over_ntsc(self) -> None:
        manifest = self.build(
            [
                entry(
                    "pal",
                    "After Burner",
                    "Amiga",
                    "WHDLOAD/OCS/A/AfterBurner",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="OCS",
                ),
                entry(
                    "ntsc",
                    "After Burner NTSC",
                    "Amiga",
                    "WHDLOAD/OCS/A/AfterBurnerNTSC",
                    source="PiMiga",
                    collection="WHDLoad",
                    category="OCS",
                ),
            ]
        )
        selected = manifest["selected"][0]
        self.assertEqual(selected["candidate"]["assets"][0]["id"], "pal")
        self.assertFalse(selected["reviewRequired"])

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

    def test_c64_tie_is_deferred_to_phase_2(self) -> None:
        manifest = self.build(
            [
                entry("one", "Example", "c64", "c64/Example.zip"),
                entry("two", "Example (Alt)", "c64", "c64/Example (Alt).zip"),
            ]
        )
        disposition = manifest["needsReview"][0]["reviewDisposition"]
        self.assertEqual(disposition["actions"][0]["queue"], "c64-release-validation")
        self.assertEqual(disposition["actions"][0]["targetPhase"], 2)

    def test_each_review_reason_gets_a_disposition(self) -> None:
        manifest = self.build(
            [
                entry(
                    "one",
                    "Example",
                    "Amiga",
                    "Installed/Example",
                    source="PiMiga",
                    collection="Installed",
                    category="Direct",
                ),
                entry(
                    "two",
                    "Example Alt",
                    "Amiga",
                    "Installed/ExampleAlt",
                    source="PiMiga",
                    collection="Installed",
                    category="Direct",
                ),
            ]
        )
        record = manifest["needsReview"][0]
        self.assertEqual(
            [action["reason"] for action in record["reviewDisposition"]["actions"]],
            record["reviewReasons"],
        )
        self.assertEqual(manifest["summary"]["phase1BlockingReviews"], 0)
        self.assertEqual(audit_manifest(manifest), [])

    def test_audit_rejects_missing_review_disposition(self) -> None:
        manifest = self.build(
            [
                entry("one", "Example", "c64", "c64/Example.zip"),
                entry("two", "Example (Alt)", "c64", "c64/Example (Alt).zip"),
            ]
        )
        del manifest["selected"][0]["reviewDisposition"]
        failures = audit_manifest(manifest)
        self.assertTrue(any("has no review disposition" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
