"""Build an explicit public allowlist; never archive a user's working directory."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = [
    ".gitignore", ".agents/plugins/marketplace.json", ".codex-plugin/plugin.json",
    ".github/workflows/test.yml", "AGENTS.md", "CLAUDE.md", "README.md", "LICENSE",
    "PRIVACY.md", "SECURITY.md", "CONTRIBUTING.md", "PUBLISHING.md", "VALIDATION.md",
    "plugin.json", "pyproject.toml", "assets/icon.svg", "assets/folio-atlas-banner.gif",
    "assets/folio-atlas-banner.png", "assets/folio-atlas-banner.svg",
    "folio_atlas/__init__.py", "folio_atlas/cli.py", "folio_atlas/organizer.py",
    "folio_atlas/backup.py", "folio_atlas/library.html", "scripts/folio.py",
    "docs/GETTING-STARTED.md", "docs/COMMANDS.md", "docs/SCHEMA.md", "docs/SAFETY.md",
    "docs/GOOGLE-DRIVE.md", "docs/DEMO.md",
    "tests/test_organizer.py", "tests/test_backup.py", "tests/test_refresh.py",
    "tests/test_index.cjs", "tools/build_release.py", "tools/check_package.py",
    "tools/create_demo.py", "tools/render_banner.py",
    "skills/folio-sort/references/workflow.md",
    "skills/folio-archive/references/cloud-protocol.md",
] + [f"skills/{skill}/{name}" for skill in ("folio-sort", "folio-refresh", "folio-archive")
     for name in ("SKILL.md", "agents/openai.yaml", "scripts/run.py")]
BINARY = {"assets/folio-atlas-banner.gif", "assets/folio-atlas-banner.png"}
PATTERNS = {
    "absolute Windows user path": r"[A-Za-z]:[/\\]Users[/\\][A-Za-z0-9_-]+",
    "absolute macOS user path": r"/Users/[A-Za-z0-9_-]+/",
    "absolute Linux home path": r"/home/[A-Za-z0-9_-]+/",
    "credential-like material": r"(?:sk-[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)",
}


def public_files():
    result = []
    if len(set(PUBLIC_FILES)) != len(PUBLIC_FILES): raise ValueError("Duplicate public allowlist entries.")
    for name in PUBLIC_FILES:
        path = ROOT / name
        if not path.is_file() or path.is_symlink(): raise ValueError("Missing or linked public file: " + name)
        if any(parent.is_symlink() for parent in path.parents): raise ValueError("Linked package ancestor.")
        data = path.read_bytes()
        if name not in BINARY:
            text = data.decode("utf-8")
            for label, pattern in PATTERNS.items():
                if re.search(pattern, text): raise ValueError("Privacy check failed: " + label + " in " + name)
        result.append((name, data))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="New directory outside the source repository")
    args = parser.parse_args()
    out = Path(args.out).expanduser().absolute()
    if any(p.is_symlink() for p in [out, *out.parents]): raise SystemExit("Output cannot be linked.")
    out = out.resolve()
    if out == ROOT or out.is_relative_to(ROOT) or out.exists():
        raise SystemExit("Choose a NEW output directory outside the repository.")
    files = public_files(); meta = json.loads(dict(files)["plugin.json"])
    version = meta["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version): raise SystemExit("Use a semantic release version.")
    out.mkdir(parents=True, exist_ok=False)
    archive = out / f"folio-atlas-{version}.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files):
            info = zipfile.ZipInfo("folio-atlas/" + name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o644 << 16
            z.writestr(info, data)
    inventory = {"version": version, "privacy_scan": "passed", "packaging": "explicit public allowlist",
                 "contains_runtime_data": False, "file": archive.name,
                 "bytes": archive.stat().st_size, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                 "files": [{"path": n, "bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()} for n,d in sorted(files)]}
    with (out / "release-inventory.json").open("x",encoding="utf-8") as f: json.dump(inventory,f,indent=2); f.write("\n")
    with (out / "SHA256SUMS.txt").open("x",encoding="utf-8") as f: f.write(inventory["sha256"] + "  " + archive.name + "\n")
    print(json.dumps({"archive": str(archive), "files": len(files), "sha256": inventory["sha256"], "privacy_scan": "passed"},indent=2))


if __name__ == "__main__": main()
