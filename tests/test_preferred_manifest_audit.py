import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_preferred_manifest import audit_manifest


def candidate(priority: list[int], language: str | None = None) -> dict:
    return {
        "priority": priority,
        "language": language,
        "releaseIdentity": "example",
        "category": "OCS",
        "assets": [{"id": "selected", "path": "example"}],
    }


class PreferredManifestAuditTests(unittest.TestCase):
    def manifest(self, selected: dict, rejected: dict) -> dict:
        return {
            "selected": [selected],
            "rejected": [rejected],
            "needsReview": [],
            "extras": [],
            "excluded": [],
        }

    def test_lower_priority_requires_manual_override(self) -> None:
        selected = {
            "groupKey": "amiga:example",
            "language": None,
            "candidate": candidate([1]),
        }
        rejected = {
            "groupKey": "amiga:example",
            "candidate": candidate([0]),
        }

        failures = audit_manifest(self.manifest(selected, rejected))

        self.assertIn("amiga:example selected a lower-priority candidate", failures)

    def test_valid_manual_override_allows_lower_priority(self) -> None:
        selected = {
            "groupKey": "amiga:example",
            "language": None,
            "candidate": candidate([1]),
            "manualOverride": {
                "selector": {"releaseIdentity": "example", "category": "OCS"},
                "resolves": ["competing-amiga-hardware-editions"],
                "rationale": "Reviewed choice.",
                "evidence": ["https://example.invalid/review"],
            },
        }
        rejected_candidate = candidate([0])
        rejected_candidate["assets"][0]["id"] = "rejected"
        rejected = {
            "groupKey": "amiga:example",
            "candidate": rejected_candidate,
        }

        failures = audit_manifest(self.manifest(selected, rejected))

        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
