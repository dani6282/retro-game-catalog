import tempfile
import unittest
from pathlib import Path

from scripts.woodstock_inventory import directory_stats


class DirectoryStatsTests(unittest.TestCase):
    def test_artwork_only_directory_is_not_launchable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Path(temp_dir)
            (package / "igame.iff").write_bytes(b"artwork")

            size, file_count, has_launchable = directory_stats(package)

        self.assertEqual(size, 7)
        self.assertEqual(file_count, 1)
        self.assertFalse(has_launchable)

    def test_nested_whdload_slave_is_launchable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Path(temp_dir)
            data_dir = package / "data"
            data_dir.mkdir()
            (package / "Game.Slave").write_bytes(b"slave")
            (data_dir / "disk.1").write_bytes(b"game-data")

            size, file_count, has_launchable = directory_stats(package)

        self.assertEqual(size, 14)
        self.assertEqual(file_count, 2)
        self.assertTrue(has_launchable)


if __name__ == "__main__":
    unittest.main()
