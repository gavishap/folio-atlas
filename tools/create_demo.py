"""Create fictional projects and downloads; never inspect a user's real folders."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import wave
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from folio_atlas.organizer import root_path


def pdf(title):
    text = title.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 22 Tf 55 740 Td ({text}) Tj 0 -40 Td /F1 12 Tf (Fictional Folio Atlas demonstration. No personal data.) Tj ET".encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    data = b"%PDF-1.4\n"; offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data)); data += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(data); data += b"xref\n0 6\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    return data + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()


def png(width=160, height=100):
    def chunk(tag, content):
        return struct.pack(">I", len(content)) + tag + content + struct.pack(">I", zlib.crc32(tag + content) & 0xffffffff)
    rows = b"".join(b"\0" + bytes((18, 61, 53)) * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def cli(*args):
    p = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/folio.py"), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if p.returncode: raise SystemExit(p.stderr + p.stdout)
    return json.loads(p.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out")
    parser.add_argument("--organize", action="store_true")
    parser.add_argument("--add-arrivals")
    args = parser.parse_args()
    if args.add_arrivals:
        base = root_path(args.add_arrivals)
        marker = base / "FOLIO-DEMO.json"
        if not marker.is_file() or json.loads(marker.read_text()).get("synthetic") is not True:
            raise SystemExit("Arrivals require a Folio-generated fictional demo folder.")
        inbox = root_path(base / "Inbox")
        for name, content in [("Juniper Studio campaign revision.pdf", pdf("Juniper Studio revision")),
                              ("Harbor Ledger updated cashflow.csv", b"month,amount\nMay,1800\nJune,2300\n")]:
            with (inbox / name).open("xb") as f: f.write(content)
        print(json.dumps({"synthetic": True, "new_files": 2, "target": str(inbox)}, indent=2)); return
    if not args.out: parser.error("Use --out NEW_FOLDER or --add-arrivals EXISTING_DEMO.")
    base = Path(args.out).expanduser().absolute()
    if base.exists() or base == ROOT or base.is_relative_to(ROOT):
        raise SystemExit("Choose a NEW folder outside the repository.")
    from folio_atlas.backup import ordinary
    base = ordinary(base, directory=True, missing=True); base.mkdir(parents=True, exist_ok=False)
    inbox = base / "Inbox"; inbox.mkdir()
    projects = base / "Projects"; projects.mkdir()
    for project, words in [("Juniper Studio", "storyboard campaign typography"), ("Harbor Ledger", "cashflow treasury forecast")]:
        folder = projects / project; folder.mkdir()
        for i in range(3):
            (folder / f"{project} {words} {i + 1}.md").write_text(f"# {project}\nFictional {words} reference {i + 1}.\n", encoding="utf-8")
    contract = pdf("Juniper Studio campaign contract")
    (projects / "Juniper Studio" / "campaign contract.pdf").write_bytes(contract)
    (inbox / "Juniper Studio campaign contract.pdf").write_bytes(contract)
    (inbox / "storyboard campaign typography review.md").write_text("Fictional creative review.\n" * 12, encoding="utf-8")
    (inbox / "Harbor Ledger cashflow forecast.csv").write_text("month,revenue,cost\nApril,2400,900\nMay,3100,1200\n", encoding="utf-8")
    (inbox / "cashflow treasury forecast summary.txt").write_text("Fictional financial planning notes.\n" * 8, encoding="utf-8")
    (inbox / "Taylor Example resume.pdf").write_bytes(pdf("Taylor Example - fictional resume"))
    (inbox / "untitled conference notes.txt").write_text("Fictional conference notes.\n" * 4, encoding="utf-8")
    (inbox / "Juniper Studio palette.png").write_bytes(png())
    with wave.open(str(inbox / "WhatsApp Audio sample.wav"), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000); f.writeframes(b"\0\0" * 16000)
    bundle = inbox / "Workshop Materials"; bundle.mkdir()
    (bundle / "schedule.pdf").write_bytes(pdf("Fictional workshop schedule"))
    (bundle / "notes.txt").write_text("Keep this folder together.\n", encoding="utf-8")
    resources = inbox / "Design Reference_files"; resources.mkdir()
    (resources / "style.css").write_text("body { color: #123d35; }", encoding="utf-8")
    (inbox / "Design Reference.html").write_text('<!doctype html><title>Fictional reference</title><link rel="stylesheet" href="Design Reference_files/style.css"><h1>Fictional reference</h1>', encoding="utf-8")
    (inbox / "KEEP LOCAL.zip").write_bytes(b"Fictional protected demonstration artifact; not a real ZIP.")
    for i, file in enumerate(sorted(inbox.rglob("*"))):
        if file.is_file():
            epoch = time.time_ns() - (i + 1) * 86400 * 1_000_000_000
            os.utime(file, ns=(epoch, epoch))
    (base / "FOLIO-DEMO.json").write_text(json.dumps({"synthetic": True, "generator": "folio-atlas-1"}), encoding="utf-8")
    result = {"synthetic": True, "target": str(inbox), "reference_projects": str(projects)}
    if args.organize:
        cli("learn", "--target", inbox, "--container", projects)
        from folio_atlas import organizer as org
        schema = inbox / org.STATE / "schema.json"
        data = org.read_json(schema); data["keep_names"] = ["KEEP LOCAL.zip"]; org.save_json(schema, data)
        plan = cli("preview", "--target", inbox)
        applied = cli("apply", "--target", inbox, "--plan", Path(plan["plan"]).name)
        verified = cli("verify", "--target", inbox, "--plan", Path(plan["plan"]).name)
        result.update(preview=plan, apply=applied, verify=verified)
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
