import json
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "test-runs" / ("refresh-" + uuid.uuid4().hex)


class RefreshTests(unittest.TestCase):
    def test_reuses_schema_and_never_rearranges_existing_library(self):
        folder = RUN / "Inbox"; folder.mkdir(parents=True)
        projects = RUN / "Projects"; project = projects / "Juniper Studio"; project.mkdir(parents=True)
        (project / "juniper typography palette.txt").write_text("synthetic")
        (project / "juniper palette typography.md").write_text("synthetic two")
        (folder / "Juniper Studio contract.pdf").write_text("synthetic first")
        def cli(*args):
            p = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/folio.py"), *args,
                                "--target", str(folder)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(p.returncode, 0, p.stderr); return json.loads(p.stdout)
        cli("learn", "--container", str(projects))
        first = cli("preview"); cli("apply", "--plan", Path(first["plan"]).name)
        first_data = json.loads(Path(first["plan"]).read_text())
        first_file = folder / first_data["moves"][0]["destination"]
        original_identity = first_file.stat().st_ino
        schema = folder / ".folio-atlas/schema.json"
        schema.write_text(json.dumps({"topics": [{"folder": "Design Research", "extensions": [".pdf"],
                                                "terms": ["typography", "palette"], "minimum_matches": 2}], "keep_names": ["keep.txt"]}))
        (folder / "Juniper Studio typography palette.pdf").write_text("synthetic second")
        (folder / "keep.txt").write_text("protected")
        (folder / "still-downloading.zip.crdownload").write_text("partial")
        fresh = cli("refresh")
        plan = json.loads(Path(fresh["plan"]).read_text())
        self.assertEqual([m["source"] for m in plan["moves"]], ["Juniper Studio typography palette.pdf"])
        self.assertIn("Projects/Juniper Studio/PDFs/Design Research", plan["moves"][0]["destination"])
        cli("apply", "--plan", Path(fresh["plan"]).name)
        self.assertEqual(first_file.stat().st_ino, original_identity)
        self.assertTrue((folder / "keep.txt").exists())
        self.assertTrue((folder / "still-downloading.zip.crdownload").exists())


if __name__ == "__main__": unittest.main()
