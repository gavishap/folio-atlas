"""Check the portable package and skill instructions without external dependencies."""
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
from build_release import ROOT, PUBLIC_FILES, public_files


def main():
    files = dict(public_files())
    plugin = json.loads(files["plugin.json"])
    compat = json.loads(files[".codex-plugin/plugin.json"])
    market = json.loads(files[".agents/plugins/marketplace.json"])
    assert plugin["name"] == compat["name"] == "folio-atlas"
    assert plugin["version"] == compat["version"] == "1.0.0"
    assert compat["skills"] == "./skills/"
    assert market["plugins"][0]["source"] == {"source": "local", "path": "./"}
    ui = plugin["extensions"]["com.openai"]["interface"]
    assert len(ui["displayName"]) <= 30 and len(ui["shortDescription"]) <= 30
    assert ui["logo"].removeprefix("./") in PUBLIC_FILES
    for skill in ("folio-sort", "folio-refresh", "folio-archive"):
        text = files[f"skills/{skill}/SKILL.md"].decode()
        assert text.startswith("---\n") and f"\nname: {skill}\n" in text
        assert re.search(r"(?m)^description: .{40,}", text)
        yaml = files[f"skills/{skill}/agents/openai.yaml"].decode()
        assert "$" + skill in yaml
        assert "allow_implicit_invocation: false" in yaml if skill == "folio-archive" else "allow_implicit_invocation: true" in yaml
        p = subprocess.run([sys.executable, str(ROOT/f"skills/{skill}/scripts/run.py"), "--version"], capture_output=True,text=True)
        assert p.returncode == 0 and p.stdout.strip() == plugin["version"]
    for name, raw in files.items():
        if not name.endswith(".md"): continue
        text = raw.decode("utf-8")
        for value in re.findall(r"\]\(([^\n)]+)\)", text) + re.findall(r'(?:src|href)="([^"]+)"', text):
            if value.startswith(("http://", "https://", "#", "<")): continue
            rel = unquote(urlsplit(value).path)
            target = (ROOT/name).parent/rel
            assert target.resolve().is_relative_to(ROOT), f"Escaping documentation link: {name}: {value}"
            assert target.exists(), f"Missing documentation link: {name}: {value}"
    print(f"Package, three skills, documentation links, entry points, and {len(files)} public files passed.")


if __name__ == "__main__": main()
