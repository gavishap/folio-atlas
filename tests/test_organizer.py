"""Behavioral tests using freshly created synthetic folders; no original folders deleted."""
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "folio_atlas/organizer.py"
SPEC = importlib.util.spec_from_file_location("organizer", SCRIPT)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
RUN = REPO / "test-runs" / uuid.uuid4().hex
RUN.mkdir(parents=True)


def put(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))
    return path


def hashes(root):
    return sorted(hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*")
                  if p.is_file() and TOOL.STATE not in p.parts and not p.name.startswith("START HERE -"))


class OrganizerTests(unittest.TestCase):
    def setUp(self):
        self.area = RUN / self._testMethodName
        self.root = self.area / "Inbox"
        self.root.mkdir(parents=True)

    def cli(self, command, *args, success=True):
        process = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), command,
                                  "--target", str(self.root), *map(str, args)],
                                 capture_output=True, text=True, encoding="utf-8")
        if success:
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        else:
            self.assertNotEqual(process.returncode, 0)
        return process

    def plan(self):
        state = self.root / TOOL.STATE
        name = json.loads((state / "latest-plan.json").read_text(encoding="utf-8"))["file"]
        return state / name, json.loads((state / name).read_text(encoding="utf-8"))

    def types(self):
        self.cli("preview", "--types-only")
        return self.plan()

    def test_project_type_bundle_preservation_and_undo(self):
        one = self.area / "References" / "Lumen Orchard"
        two = self.area / "References" / "Cobalt Harbor"
        put(one / "orchard pollination calendar.txt", "orchard pollination irrigation calendar")
        put(one / "orchard irrigation schedule.txt", "orchard irrigation pollination schedule")
        put(two / "harbor cargo tides.txt", "harbor cargo tides mooring")
        put(two / "harbor mooring schedule.txt", "harbor cargo mooring schedule")
        put(self.root / "Lumen Orchard contract.pdf", "synthetic agreement")
        put(self.root / "résumé.pdf", "synthetic resume")
        put(self.root / "resume.pdf", "another synthetic resume")
        put(self.root / "WhatsApp Audio.opus", "synthetic audio")
        put(self.root / "leads.csv", "name,company\nExample,Demo")
        put(self.root / "Bundle" / "keep.txt", "preserved bundle")
        put(self.root / "page.html", '<img src="page_files/a.png">')
        put(self.root / "page_files" / "a.png", "synthetic image")
        put(self.root / "package.json", '{"name":"demo-source"}')
        put(self.root / "src" / "app.js", "console.log('synthetic');")
        put(self.root / ".env", "fictional-placeholder")
        (self.root / "Empty Bundle").mkdir()
        baseline = hashes(self.root)
        self.cli("learn", "--project", one, "--project", two)
        self.cli("preview")
        plan_path, plan = self.plan()
        lookup = {m["source"]: m for m in plan["moves"]}
        self.assertEqual(lookup["Lumen Orchard contract.pdf"]["project"], "Lumen Orchard")
        self.assertIn("PDFs/Resumes", lookup["resume.pdf"]["destination"])
        self.assertIn("WhatsApp Recordings", lookup["WhatsApp Audio.opus"]["destination"])
        self.assertIn("Excels/Lead Lists", lookup["leads.csv"]["destination"])
        self.assertIn("Configuration and Credentials", lookup[".env"]["destination"])
        self.assertEqual(Path(lookup["page.html"]["destination"]).parent,
                         Path(lookup["page_files"]["destination"]).parent)
        self.assertEqual(Path(lookup["package.json"]["destination"]).parent,
                         Path(lookup["src"]["destination"]).parent)
        self.cli("apply", "--plan", plan_path.name)
        self.cli("verify", "--plan", plan_path.name)
        self.assertEqual(hashes(self.root), baseline)
        index_name = json.loads((self.root / TOOL.STATE / "owner.json").read_text(encoding="utf-8"))["index"]
        index = (self.root / index_name).read_text(encoding="utf-8")
        data = json.loads(re.search(r'<script id="file-data" type="application/json">([\s\S]*?)</script>', index).group(1))
        self.assertTrue(any(row["name"] == "Bundle" for row in data["bundles"]))
        self.assertTrue(any(row["path"].endswith("Bundle/keep.txt") for row in data["files"]))
        self.cli("undo", "--plan", plan_path.name)
        self.cli("verify", "--plan", plan_path.name)
        self.assertEqual(hashes(self.root), baseline)
        self.assertTrue((self.root / "Bundle" / "keep.txt").is_file())
        self.assertTrue((self.root / "Empty Bundle").is_dir())

    def test_ambiguous_projects_fall_back(self):
        one, two = self.area / "Lumen Orchard", self.area / "Cobalt Harbor"
        put(one / "shared.txt", "identical synthetic document")
        put(two / "shared.txt", "identical synthetic document")
        put(self.root / "shared.txt", "identical synthetic document")
        put(self.root / "Lumen Orchard Cobalt Harbor.pdf", "conflicting names")
        self.cli("learn", "--project", one, "--project", two)
        self.cli("preview")
        self.assertTrue(all(m["project"] is None for m in self.plan()[1]["moves"]))

    def test_exact_fingerprint(self):
        project = self.area / "Lumen Orchard"
        put(project / "reference.txt", "a unique synthetic project reference")
        put(self.root / "unlabeled.txt", "a unique synthetic project reference")
        self.cli("learn", "--project", project)
        self.cli("preview")
        self.assertEqual(self.plan()[1]["moves"][0]["project"], "Lumen Orchard")

    def test_empty_fingerprint_is_not_project_evidence(self):
        project = self.area / "Lumen Orchard"
        put(project / "empty.txt", "")
        put(self.root / "unrelated.txt", "")
        self.cli("learn", "--project", project)
        self.cli("preview")
        self.assertIsNone(self.plan()[1]["moves"][0]["project"])

    def test_shared_html_resources_and_file_count(self):
        project = self.area / "Lumen Orchard"
        put(project / "one file.txt", "one")
        put(project / "second multiword file.txt", "two")
        learned = json.loads(self.cli("learn", "--project", project).stdout)
        self.assertEqual(learned["sampled_files"], 2)
        put(self.root / "Page.html", "synthetic html")
        put(self.root / "Page.htm", "synthetic htm")
        put(self.root / "Page_files" / "image.png", "synthetic image")
        self.cli("preview")
        moves = self.plan()[1]["moves"]
        self.assertEqual(len({m["source"] for m in moves}), 3)
        self.assertEqual(len({str(Path(m["destination"]).parent) for m in moves}), 1)
        self.cli("apply")
        self.cli("verify")

    def test_reference_links_refused(self):
        reference = self.area / "Reference"
        put(reference / "a.txt", "synthetic")
        alias = self.area / "Reference Link"
        try:
            os.symlink(reference, alias, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Host does not allow synthetic symlinks: {exc}")
        self.cli("learn", "--project", alias, success=False)

    def test_optional_document_vocabulary(self):
        project = self.area / "Quartz Ecology"
        text = "mycorrhizal symbiosis rhizosphere propagation"
        put(project / "one.txt", text)
        put(project / "two.txt", text)
        put(self.root / "notes.txt", text + " target-specific additional sentence")
        self.cli("learn", "--project", project, "--read-documents")
        self.cli("preview")
        self.assertIsNone(self.plan()[1]["moves"][0]["project"])
        self.cli("preview", "--read-documents")
        self.assertEqual(self.plan()[1]["moves"][0]["project"], "Quartz Ecology")

    def test_stale_file_refused_before_any_move(self):
        put(self.root / "a.txt", "before")
        put(self.root / "b.txt", "stable")
        self.types()
        put(self.root / "a.txt", "changed content")
        self.cli("apply", success=False)
        self.assertTrue((self.root / "a.txt").exists())
        self.assertTrue((self.root / "b.txt").exists())

    def test_new_bundle_child_refused(self):
        put(self.root / "Bundle" / "a.txt", "before")
        self.types()
        put(self.root / "Bundle" / "new.txt", "new after preview")
        self.cli("apply", success=False)
        self.assertTrue((self.root / "Bundle" / "a.txt").exists())

    def test_no_overwrite_and_collision_suffix(self):
        put(self.root / "a.txt", "original")
        _, first = self.types()
        destination = self.root / first["moves"][0]["destination"]
        put(destination, "existing occupant")
        self.cli("apply", success=False)
        self.assertEqual(destination.read_text(encoding="utf-8"), "existing occupant")
        self.cli("preview", "--types-only")
        self.assertIn("a (2).txt", self.plan()[1]["moves"][0]["destination"])
        self.cli("apply")
        self.assertEqual(destination.read_text(encoding="utf-8"), "existing occupant")

    def test_occupied_source_blocks_undo(self):
        put(self.root / "a.txt", "original")
        self.types()
        self.cli("apply")
        put(self.root / "a.txt", "new occupant")
        self.cli("undo", success=False)
        self.assertEqual((self.root / "a.txt").read_text(encoding="utf-8"), "new occupant")

    def test_changed_payload_blocks_undo(self):
        put(self.root / "Bundle" / "a.txt", "original")
        _, plan = self.types()
        self.cli("apply")
        destination = self.root / plan["moves"][0]["destination"]
        put(destination / "a.txt", "edited after organization")
        self.cli("undo", success=False)
        self.assertFalse((self.root / "Bundle").exists())

    def test_crash_after_intent_before_done_resumes(self):
        put(self.root / "a.txt", "original")
        _, plan = self.types()
        move = plan["moves"][0]
        destination = self.root / move["destination"]
        destination.parent.mkdir(parents=True)
        journal = self.root / TOOL.STATE / f"journal-{plan['id']}.jsonl"
        TOOL.journal_append(journal, {"event": "intent", **move})
        TOOL.no_replace(self.root / move["source"], destination)
        self.cli("apply")
        self.cli("verify")
        self.cli("undo")
        self.assertEqual((self.root / "a.txt").read_text(encoding="utf-8"), "original")

    def test_index_name_is_reserved_and_replacement_refused(self):
        put(self.root / "START HERE - Downloads Organizer.html", "existing original index name")
        put(self.root / "a.txt", "original")
        self.cli("learn")
        cfg = json.loads((self.root / TOOL.STATE / "owner.json").read_text(encoding="utf-8"))
        index = self.root / cfg["index"]
        self.assertNotEqual(cfg["index"], "START HERE - Downloads Organizer.html")
        self.assertTrue(index.exists())
        moved_aside = self.root / "old-tool-index.html"
        index.rename(moved_aside)
        put(index, "new occupant")
        self.cli("index", success=False)
        self.assertEqual(index.read_text(encoding="utf-8"), "new occupant")

    def test_link_bundle_stays_at_source(self):
        outside = put(self.area / "Outside" / "keep.txt", "outside remains")
        (self.root / "Bundle").mkdir()
        try:
            os.symlink(outside, self.root / "Bundle" / "link.txt")
        except OSError as exc:
            self.skipTest(f"Host does not allow synthetic symlinks: {exc}")
        _, plan = self.types()
        self.assertFalse(plan["moves"])
        self.assertEqual(len(plan["skipped"]), 1)
        self.cli("apply")
        self.assertTrue((self.root / "Bundle").is_dir())
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside remains")

    def test_tampered_escape_plan_refused(self):
        put(self.root / "a.txt", "original")
        plan_path, plan = self.types()
        plan["moves"][0]["destination"] = "../Outside/a.txt"
        plan_path.write_text(json.dumps(plan))
        self.cli("apply", success=False)
        self.assertTrue((self.root / "a.txt").exists())

    def test_csv_formula_filename_and_html_escaping(self):
        put(self.root / "=SUM(1).txt", "synthetic formula filename")
        put(self.root / "a&b.txt", "synthetic ampersand")
        plan_path, _ = self.types()
        text = plan_path.with_suffix(".csv").read_text(encoding="utf-8-sig")
        self.assertIn("'=SUM(1).txt", text)
        self.cli("apply")
        cfg = json.loads((self.root / TOOL.STATE / "owner.json").read_text(encoding="utf-8"))
        page = (self.root / cfg["index"]).read_text(encoding="utf-8")
        data = json.loads(re.search(r'<script id="file-data" type="application/json">([\s\S]*?)</script>', page).group(1))
        self.assertTrue(any(row["name"] == "a&b.txt" and "%26" in row["url"] for row in data["files"]))
        self.assertIn("a%26b.txt", page)


if __name__ == "__main__":
    print("Synthetic fixtures retained in a fresh test-runs directory.")
    unittest.main(verbosity=2)
