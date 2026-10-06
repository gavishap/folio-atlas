"""Backup and deletion gates, using only explicitly created synthetic folders."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from folio_atlas import organizer, backup
RUN = REPO / "test-runs" / ("backup-" + uuid.uuid4().hex)
RUN.mkdir(parents=True)
CLI = REPO / "scripts/folio.py"


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.base = RUN / self._testMethodName
        self.root = self.base / "Inbox"; self.root.mkdir(parents=True)
        (self.root / "report #1 & 100%.txt").write_text("synthetic source", encoding="utf-8")
        (self.root / "Empty Folder").mkdir()
        self.out = self.base / "Backup Work"

    def cli(self, *argv, success=True):
        result = subprocess.run([sys.executable, "-X", "utf8", str(CLI), *map(str, argv)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode == 0, success, result.stderr + result.stdout[:1000])
        return json.loads(result.stdout) if success else result

    def build(self, sorted_library=False):
        if sorted_library:
            p = self.cli("preview", "--target", self.root, "--types-only")
            self.cli("apply", "--target", self.root, "--plan", Path(p["plan"]).name)
        self.built = self.cli("backup", "build", "--target", self.root, "--out", self.out)
        return self.built

    def roundtrip(self, sorted_library=False):
        self.build(sorted_library)
        self.download = self.base / "Downloaded from cloud.zip"
        shutil.copyfile(self.built["archive"], self.download)
        self.restored = self.base / "New Restore"
        self.proof = self.cli("backup", "verify-roundtrip", "--build", self.built["build_receipt"],
                              "--downloaded", self.download, "--restore-to", self.restored,
                              "--cloud-url", "https://drive.google.com/file/d/synthetic-id/view")
        return self.proof

    def cleanup_plan(self, scope="copies", *extra):
        return self.cli("backup", "cleanup-preview", "--receipt", self.proof["roundtrip_receipt"], "--scope", scope, *extra)

    def clean(self, plan, *extra, success=True):
        return self.cli("backup", "cleanup", "--plan", plan["plan"], "--confirm", plan["confirmation_id"], *extra, success=success)

    def test_full_roundtrip_and_index_reserved_names(self):
        p = self.roundtrip(True)
        self.assertTrue(p["complete"])
        self.assertTrue(p["index"]["dates_and_sizes_match"])
        self.assertGreater(p["index"]["links_checked"], 0)
        self.assertTrue((Path(p["restored_library"]) / "Folio Library").is_dir())

    def test_original_local_zip_is_not_cloud_evidence(self):
        self.build()
        self.cli("backup", "verify-roundtrip", "--build", self.built["build_receipt"],
                 "--downloaded", self.built["archive"], "--restore-to", self.base / "Restore",
                 "--cloud-url", "https://drive.google.com/file/d/synthetic/view", success=False)
        self.assertTrue((self.root / "report #1 & 100%.txt").exists())

    def test_corrupt_download_preserves_every_original(self):
        self.build(); path = self.base / "Broken.zip"
        path.write_bytes(Path(self.built["archive"]).read_bytes() + b"changed")
        self.cli("backup", "verify-roundtrip", "--build", self.built["build_receipt"],
                 "--downloaded", path, "--restore-to", self.base / "Restore",
                 "--cloud-url", "https://drive.google.com/file/d/synthetic/view", success=False)
        self.assertFalse((self.base / "Restore").exists())
        self.assertTrue((self.root / "report #1 & 100%.txt").exists())

    def test_existing_restore_folder_never_overwritten(self):
        self.build(); path = self.base / "Download.zip"; shutil.copyfile(self.built["archive"], path)
        destination = self.base / "Restore"; destination.mkdir(); (destination / "keep.txt").write_text("new")
        self.cli("backup", "verify-roundtrip", "--build", self.built["build_receipt"],
                 "--downloaded", path, "--restore-to", destination,
                 "--cloud-url", "https://drive.google.com/file/d/synthetic/view", success=False)
        self.assertEqual((destination / "keep.txt").read_text(encoding="utf-8"), "new")

    def test_copies_cleanup_requires_cloud_presence_confirmation(self):
        self.roundtrip(); plan = self.cleanup_plan()
        self.clean(plan, success=False)
        self.assertTrue(Path(self.built["archive"]).exists())

    def test_copies_cleanup_preserves_originals(self):
        self.roundtrip(); plan = self.cleanup_plan()
        result = self.clean(plan, "--cloud-available")
        self.assertFalse(Path(self.built["archive"]).exists())
        self.assertFalse(self.download.exists())
        self.assertFalse(self.restored.exists())
        self.assertTrue((self.root / "report #1 & 100%.txt").exists())
        self.assertTrue(Path(result["receipt"]).exists())

    def test_original_cleanup_needs_separate_flag(self):
        self.roundtrip(); plan = self.cleanup_plan("originals")
        self.clean(plan, "--cloud-available", success=False)
        self.assertTrue((self.root / "report #1 & 100%.txt").exists())

    def test_changed_original_and_new_files_are_preserved(self):
        self.roundtrip(); original = self.root / "report #1 & 100%.txt"
        original.write_text("changed by user")
        (self.root / "new.txt").write_text("newly downloaded")
        plan = self.cleanup_plan("originals")
        self.clean(plan, "--cloud-available", "--delete-originals")
        self.assertEqual(original.read_text(encoding="utf-8"), "changed by user")
        self.assertEqual((self.root / "new.txt").read_text(encoding="utf-8"), "newly downloaded")

    def test_change_after_cleanup_preview_is_preserved(self):
        self.roundtrip(); plan = self.cleanup_plan("originals")
        original = self.root / "report #1 & 100%.txt"; original.write_text("later edit")
        result = self.clean(plan, "--cloud-available", "--delete-originals")
        self.assertEqual(original.read_text(encoding="utf-8"), "later edit")
        self.assertTrue(result["preserved"])

    def test_keep_filename_is_unconditional(self):
        keep = self.root / "KEEP.zip"; keep.write_bytes(b"synthetic protected file")
        self.roundtrip(); plan = self.cleanup_plan("all", "--keep", "KEEP.zip")
        self.clean(plan, "--cloud-available", "--delete-originals")
        self.assertEqual(keep.read_bytes(), b"synthetic protected file")
        self.assertTrue(self.root.is_dir())

    def test_new_restored_content_keeps_its_parent(self):
        self.roundtrip(); new = self.restored / "Library" / "new.txt"; new.write_text("new user content")
        plan = self.cleanup_plan()
        result = self.clean(plan, "--cloud-available")
        self.assertEqual(new.read_text(encoding="utf-8"), "new user content")
        self.assertTrue(result["preserved"])

    def test_modified_receipt_or_plan_cannot_authorize_deletion(self):
        self.roundtrip(); plan = self.cleanup_plan()
        p = Path(plan["plan"]); data = json.loads(p.read_text(encoding="utf-8")); data["source_root"] = str(self.base)
        p.write_text(json.dumps(data))
        self.clean(plan, "--cloud-available", success=False)
        self.assertTrue(Path(self.built["archive"]).exists())

    def test_backup_inside_source_is_refused(self):
        self.cli("backup", "build", "--target", self.root, "--out", self.root / "Backups", success=False)

    def test_incomplete_downloads_are_never_deleted(self):
        partial = self.root / "unfinished.crdownload"; partial.write_bytes(b"synthetic partial")
        nested = self.root / "Bundle"; nested.mkdir()
        (nested / "more.part").write_bytes(b"synthetic nested partial")
        self.roundtrip(); plan = self.cleanup_plan("originals")
        self.clean(plan, "--cloud-available", "--delete-originals")
        self.assertEqual(partial.read_bytes(), b"synthetic partial")
        self.assertEqual((nested / "more.part").read_bytes(), b"synthetic nested partial")

    def test_keep_path_escape_is_rejected(self):
        self.roundtrip()
        self.cli("backup", "cleanup-preview", "--receipt", self.proof["roundtrip_receipt"],
                 "--keep", "../outside.txt", success=False)

    def test_schema_protection_carries_into_original_cleanup(self):
        keep = self.root / "KEPT BY SCHEMA.txt"; keep.write_text("fictional protected item")
        self.roundtrip(True)
        schema_path = self.root / organizer.STATE / "schema.json"
        schema = organizer.read_json(schema_path)
        # After sorting, protect the intact managed library by its exact root name.
        schema["keep_names"] = ["Folio Library"]; organizer.save_json(schema_path, schema)
        plan = self.cleanup_plan("originals")
        self.clean(plan, "--cloud-available", "--delete-originals")
        self.assertTrue(any(p.name == keep.name for p in (self.root / "Folio Library").rglob("*")))

    def test_unsafe_zip_is_rejected_without_extraction(self):
        path = self.base / "Unsafe.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("../outside.txt", "synthetic")
        self.cli("backup", "restore", "--archive", path, "--destination", self.base / "Restore", success=False)
        self.assertFalse((self.base / "outside.txt").exists())
        self.assertFalse((self.base / "Restore").exists())

    def test_restore_elsewhere_rebinds_refresh_and_preserves_dates(self):
        self.build(True)
        restored = self.base / "Other Computer"
        p = self.cli("backup", "restore", "--archive", self.built["archive"], "--destination", restored)
        self.assertTrue(p["refresh_ready"])
        (restored / "new resume.pdf").write_text("new synthetic resume")
        preview = self.cli("refresh", "--target", restored)
        self.assertEqual(preview["moves"], 1)
        self.cli("apply", "--target", restored, "--plan", Path(preview["plan"]).name)
        cfg = organizer.read_json(restored / organizer.STATE / "owner.json")
        parser = backup.PageParser(); parser.feed((restored / cfg["index"]).read_text(encoding="utf-8"))
        self.assertGreater(len(json.loads("".join(parser.parts))["bundles"]), 0)


if __name__ == "__main__": unittest.main()
