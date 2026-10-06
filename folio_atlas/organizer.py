#!/usr/bin/env python3
"""Project-aware folder organization. Standard library; optional pypdf for PDFs."""
from __future__ import annotations

import argparse
import collections
import csv
import ctypes
import errno
import hashlib
import html
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import unicodedata
from urllib.parse import quote
import uuid
import xml.etree.ElementTree as ET
import zipfile

VERSION = "1.0.0"
STATE = ".folio-atlas"
IGNORED = {".git", ".svn", "node_modules", "venv", ".venv", "__pycache__",
           "dist", "build", ".next", ".cache", "windows", "program files",
           "program files (x86)", "programdata", "users", "$recycle.bin",
           "system volume information", "recovery", "appdata"}
STOP = set("the and for with from this that project file files document documents "
           "final draft copy version new old general report reports notes sample "
           "pdf doc docx xls xlsx csv txt json html png jpg jpeg zip readme "
           "contract agreement resume invoice proposal budget meeting download downloads".split())
SECRET = re.compile(r"(^\.env($|\.)|credential|password|secret|private.?key|"
                    r"token|passport|social.?security|patient|medical.?record)", re.I)
TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".rtf"}
DOC_EXT = TEXT_EXT | {".pdf", ".docx", ".xlsx", ".pptx"}
PARTIAL_EXT = (".crdownload", ".part", ".partial", ".download", ".tmp")


class SafetyError(RuntimeError):
    pass


def configure_output():
    # Agent shells commonly capture pipes using UTF-8, even on older Windows locales.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def read_json(path):
    if is_link(Path(path)):
        raise SafetyError("Private state files must not be links.")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, obj, exclusive=False):
    path = Path(path)
    if path.exists() and is_link(path):
        raise SafetyError("Private state files must not be links.")
    with path.open("x" if exclusive else "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def normalize(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    value = "".join(c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def terms(value):
    return {t for t in normalize(value).split() if len(t) >= 4 and not t.isdigit() and t not in STOP}


def label(value):
    result = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value).strip(" .")[:100]
    if not result or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", result):
        result = "Project-" + result
    return result


def is_link(path):
    st = path.lstat()
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)


def root_path(value):
    raw = Path(value).expanduser().absolute()
    # Inspect every component before resolving: resolve alone conceals junctions.
    for p in [raw, *raw.parents]:
        if p.exists() and is_link(p):
            raise SafetyError("Target path must not contain links or junctions.")
    root = raw.resolve(strict=True)
    if not root.is_dir() or root == Path(root.anchor) or root == Path.home().resolve():
        raise SafetyError("Choose a specific existing folder, not a drive root or home folder.")
    return root


def reference_path(value):
    raw = Path(value).expanduser().absolute()
    for p in [raw, *raw.parents]:
        if p.exists() and is_link(p):
            raise SafetyError("Reference paths must not contain links or junctions.")
    path = raw.resolve(strict=True)
    if not path.is_dir():
        raise SafetyError("Reference location must be a directory.")
    return path


def inside(root, relative):
    part = Path(relative)
    if not relative or part.is_absolute() or part.drive or ".." in part.parts:
        raise SafetyError("Unsafe relative path in plan or journal.")
    path = root / part
    for p in [path, *path.parents]:
        if p == root:
            break
        if p.exists() and is_link(p):
            raise SafetyError("Move path contains a link or junction.")
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root) or resolved == root:
        raise SafetyError("Move path escapes the target folder.")
    return path


def meta(path):
    st = path.lstat() if is_link(path) else path.stat()
    kind = "link" if is_link(path) else "dir" if stat.S_ISDIR(st.st_mode) else "file"
    if kind == "file" and not stat.S_ISREG(st.st_mode):
        kind = "special"
    return {"kind": kind, "size": st.st_size if kind == "file" else 0,
            "mtime_ns": st.st_mtime_ns if kind == "file" else 0,
            "dev": st.st_dev, "ino": st.st_ino}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def unique(path, reserved=()):
    reserved = {str(p).casefold() for p in reserved}
    candidate, n = path, 2
    while candidate.exists() or candidate.is_symlink() or str(candidate).casefold() in reserved:
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}" if path.suffix else f"{path.name} ({n})")
        n += 1
    return candidate


def state(root, create=False):
    folder = root / STATE
    marker = folder / "owner.json"
    if folder.exists():
        if is_link(folder) or not folder.is_dir() or not marker.is_file() or is_link(marker):
            raise SafetyError("Reserved state folder already exists without this tool's ownership marker.")
        cfg = read_json(marker)
        if cfg.get("tool") != "folio-atlas" or cfg.get("root") != str(root):
            raise SafetyError("State ownership does not match this target.")
        output = inside(root, cfg["output"])
        if len(Path(cfg["output"]).parts) != 1:
            raise SafetyError("Managed output must be a direct child of the target.")
        validate_index(root, cfg)
        return folder, cfg
    if not create:
        raise SafetyError("Run learn first, or run preview --types-only for a folder with no projects.")
    folder.mkdir()
    output = unique(root / "Folio Library")
    index = unique(root / "START HERE - Folio Atlas.html")
    with index.open("x", encoding="utf-8") as f:
        f.write('<!doctype html><title>Folio Atlas</title><p>Run preview, then apply to build your file index.</p>')
    cfg = {"tool": "folio-atlas", "version": VERSION, "root": str(root),
           "output": output.name, "index": index.name, "id": uuid.uuid4().hex}
    cfg["index_identity"] = {k: meta(index)[k] for k in ("dev", "ino")}
    save_json(marker, cfg, exclusive=True)
    save_json(folder / "schema.json", {"version": 1, "topics": [], "keep_names": []}, exclusive=True)
    return folder, cfg


def snapshot(root, cfg):
    result = {}
    def visit(folder):
        for p in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
            if folder == root and p.name in {STATE, cfg["index"]}:
                continue
            rel = p.relative_to(root).as_posix()
            result[rel] = meta(p)
            if result[rel]["kind"] == "dir":
                visit(p)
    visit(root)
    return result


def sample_files(root, limit=300, avoid=None):
    count = 0
    for folder, dirs, names in os.walk(root, followlinks=False):
        base = Path(folder)
        dirs[:] = sorted(d for d in dirs if d.casefold() not in IGNORED
                         and not is_link(base / d) and (avoid is None or base / d != avoid))
        for name in sorted(names):
            p = base / name
            if not is_link(p) and p.is_file():
                yield p
                count += 1
                if count >= limit:
                    return


def extract(path):
    """Bounded local text only. Never execute documents or retain extracted text."""
    if SECRET.search(path.name) or path.stat().st_size > 20 * 1024 * 1024:
        return ""
    ext = path.suffix.casefold()
    try:
        if ext in TEXT_EXT:
            with path.open("rb") as f:
                return f.read(128 * 1024).decode("utf-8", errors="replace")[:16000]
        if ext == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                return ""
            reader = PdfReader(path)
            if reader.is_encrypted:
                return ""
            return " ".join((p.extract_text() or "")[:8000] for p in reader.pages[:2])[:16000]
        if ext in {".docx", ".xlsx", ".pptx"}:
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if (
                    n == "word/document.xml" or n == "xl/sharedStrings.xml" or
                    re.fullmatch(r"ppt/slides/slide\d+\.xml", n) or
                    re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))][:5]
                pieces = []
                for name in names:
                    if z.getinfo(name).file_size > 2 * 1024 * 1024:
                        continue
                    data = z.read(name)
                    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
                        continue
                    pieces.extend(ET.fromstring(data).itertext())
                return " ".join(pieces)[:16000]
    except Exception:
        return ""
    return ""


def learn(args):
    root = root_path(args.target)
    folder, cfg = state(root, create=True)
    candidates = [reference_path(p) for p in args.project]
    for value in args.container:
        parent = reference_path(value)
        candidates.extend(p for p in sorted(parent.iterdir()) if p.is_dir()
                          and not is_link(p) and not p.name.startswith(".")
                          and p.name.casefold() not in IGNORED and p != root)
    projects, counts, sampled_total = [], [], 0
    seen = set()
    for project in candidates:
        if project in seen:
            continue
        seen.add(project)
        if not project.is_dir() or project == root or project.is_relative_to(root) or is_link(project):
            raise SafetyError("Reference projects must be ordinary folders outside the target.")
        names = list(sample_files(project, avoid=root))
        sampled_total += len(names)
        counter = collections.Counter()
        hashes = []
        docs_read = 0
        for path in names:
            relative = path.relative_to(project).as_posix()
            file_terms = terms(relative)
            if SECRET.search(path.name):
                counter.update(file_terms)
                continue
            if args.read_documents and path.suffix.casefold() in DOC_EXT and docs_read < 20:
                file_terms.update(terms(extract(path)))
                docs_read += 1
            counter.update(file_terms)
            if len(hashes) < 80 and path.suffix.casefold() in DOC_EXT and 0 < path.stat().st_size <= 20 * 1024 * 1024:
                hashes.append(digest(path))
        safe = label(project.name)
        used = {p["label"].casefold() for p in projects}
        base, n = safe, 2
        while safe.casefold() in used:
            safe = f"{base} ({n})"
            n += 1
        projects.append({"label": safe, "source": str(project), "aliases": [project.name],
                         "terms": [], "hashes": hashes, "content_phrases": [],
                         "sample_names": [p.relative_to(project).as_posix() for p in names[:30]]})
        counts.append(counter)
    shared = collections.Counter(t for c in counts for t in c)
    for project, counter in zip(projects, counts):
        project["terms"] = [t for t, n in counter.most_common() if n >= 2 and shared[t] == 1][:30]
    path = folder / "profiles.json"
    save_json(path, {"version": VERSION, "read_documents": bool(args.read_documents), "projects": projects})
    print(json.dumps({"profiles": str(path), "projects": len(projects), "sampled_files": sampled_total}, indent=2))


def subtype(name):
    text = normalize(name)
    rules = [("Resumes", r"\b(resume|resumes|cv|curriculum vitae)\b"),
             ("Contracts", r"\b(contract|agreement|nda|engagement letter|lease)\b"),
             ("Invoices and Receipts", r"\b(invoice|receipt|bill)\b"),
             ("Proposals", r"\b(proposal|quote|quotation)\b"),
             ("Finance", r"\b(budget|financial|finance|statement|tax)\b"),
             ("Learning", r"\b(course|tutorial|manual|guide|book|lesson)\b")]
    return next((category for category, pattern in rules if re.search(pattern, text)), "General")


def category(path, directory=False):
    if directory:
        return "Preserved Folders"
    ext = path.suffix.casefold()
    name = normalize(path.name)
    if SECRET.search(path.name) or ext in {".pem", ".key", ".p12", ".pfx", ".env"}:
        return "Configuration and Credentials"
    if ext == ".pdf":
        return "PDFs/" + subtype(path.stem)
    if ext in {".xlsx", ".xls", ".xlsm", ".xlsb", ".ods", ".csv", ".tsv"}:
        sub = "Lead Lists" if re.search(r"\b(lead|leads|prospect|prospects|contacts)\b", name) else subtype(path.stem)
        return "Excels/" + sub
    if ext in {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".aac", ".flac", ".wma", ".mp4", ".mov", ".mkv", ".webm", ".avi"}:
        sub = "WhatsApp Recordings" if "whatsapp" in name else "Voice Notes" if re.search(r"\b(voice|voicenote|voice note|ptt)\b", name) else "Video" if ext in {".mp4", ".mov", ".mkv", ".webm", ".avi"} else "Audio"
        return "Recordings/" + sub
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".heic", ".bmp", ".tif", ".tiff"}:
        return "Images/" + ("Screenshots" if "screenshot" in name else "General")
    if ext in {".docx", ".doc", ".odt", ".txt", ".md", ".rtf"}:
        return "Documents/" + subtype(path.stem)
    if ext in {".pptx", ".ppt", ".odp"}:
        return "Presentations"
    if ext in {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}:
        return "Archives"
    if ext in {".exe", ".msi", ".msix", ".dmg", ".pkg", ".deb", ".rpm", ".iso"}:
        return "Installers and Tools"
    if ext in {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".ps1", ".sh", ".ipynb", ".sql", ".html", ".htm", ".css"}:
        return "Code and Workflows"
    if ext in {".parquet", ".sqlite", ".db", ".npy", ".h5"}:
        return "Datasets"
    return "Other Files"


def project_match(paths, profiles, read_documents=False):
    if not profiles:
        return None, "no project references selected"
    names = " ".join(p.name for p in paths)
    # Sample bundle names, never split bundles or recurse through dependencies.
    for p in paths:
        if p.is_dir():
            names += " " + " ".join(str(q.relative_to(p)) for q in sample_files(p, limit=30))
    body = " ".join(extract(p) for p in paths if read_documents and p.is_file() and p.suffix.casefold() in DOC_EXT)
    name_text, body_text = " " + normalize(names) + " ", " " + normalize(body) + " "
    name_terms, body_terms = terms(names), terms(body)
    fingerprints = {digest(p) for p in paths if p.is_file() and p.suffix.casefold() in DOC_EXT
                    and not SECRET.search(p.name) and 0 < p.stat().st_size <= 20 * 1024 * 1024}
    scores = []
    for project in profiles:
        score, reasons = 0, []
        for alias in project.get("aliases", []):
            token = normalize(alias)
            if len(token.replace(" ", "")) >= 4 and f" {token} " in name_text:
                score += 12
                reasons.append("project name in filename or bundle")
                break
        if fingerprints.intersection(project.get("hashes", [])):
            score += 20
            reasons.append("exact content fingerprint")
        for phrase in project.get("content_phrases", []):
            token = normalize(phrase)
            if len(token.split()) >= 2 and f" {token} " in body_text:
                score += 10
                reasons.append("reviewed distinctive content phrase")
        vocabulary = set(project.get("terms", []))
        matched = vocabulary & (name_terms | body_terms)
        if len(matched) >= 3:
            score += 6 + min(len(matched), 6)
            reasons.append("multiple learned distinctive terms: " + ", ".join(sorted(matched)))
        scores.append((score, project["label"], reasons))
    scores.sort(reverse=True)
    if scores and scores[0][0] >= 9 and (len(scores) == 1 or scores[0][0] - scores[1][0] >= 4):
        return scores[0][1], "; ".join(scores[0][2])
    return None, "ambiguous project evidence" if scores and scores[0][0] >= 9 else "no confident project evidence"


def groups(items):
    """Preserve saved web-page resources and explicit loose source bundles."""
    by_name = {p.name.casefold(): p for p in items}
    claimed, result = set(), []
    for p in items:
        if p not in claimed and p.suffix.casefold() in {".html", ".htm"}:
            resource = by_name.get((p.stem + "_files").casefold())
            if resource and resource.is_dir() and resource not in claimed:
                pages = [q for q in items if q.suffix.casefold() in {".html", ".htm"}
                         and q.stem.casefold() == p.stem.casefold() and q not in claimed]
                bundle = pages + [resource]
                result.append((bundle, "Saved Web Pages/" + label(p.stem)))
                claimed.update(bundle)
    manifest = by_name.get("package.json")
    if manifest and manifest.is_file() and manifest not in claimed:
        names = {"package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                 "src", "public", "components", "app", "pages", "index.html",
                 "tsconfig.json", "vite.config.ts", "vite.config.js", "next.config.js",
                 "next.config.ts", "next.config.mjs", "node_modules"}
        bundle = [p for p in items if p.name.casefold() in names and p not in claimed]
        if any(p.is_dir() and p.name.casefold() in {"src", "app", "pages"} for p in bundle):
            result.append((bundle, "Code and Workflows/Preserved Source Bundle"))
            claimed.update(bundle)
    result.extend(([p], None) for p in items if p not in claimed)
    return result


def preview(args):
    root = root_path(args.target)
    folder, cfg = state(root, create=args.types_only)
    profiles_path = folder / "profiles.json"
    profiles = [] if args.types_only or not profiles_path.exists() else read_json(profiles_path)["projects"]
    schema_path = folder / "schema.json"
    schema = read_json(schema_path) if schema_path.exists() else {"topics": [], "keep_names": []}
    keep_names = set(schema.get("keep_names", [])) | set(args.keep)
    keep_names.update({"desktop.ini", ".DS_Store"})
    for profile in profiles:
        if label(profile["label"]) != profile["label"] or "/" in profile["label"]:
            raise SafetyError("Invalid project label in profiles.")
    before = snapshot(root, cfg)
    items = [p for p in sorted(root.iterdir(), key=lambda p: p.name.casefold())
             if p.name not in {STATE, cfg["output"], cfg["index"]} and p.name not in keep_names
             and not p.name.lower().endswith(PARTIAL_EXT)]
    # Protect the installed helper/source when users keep it inside the target.
    own = Path(__file__).resolve()
    items = [p for p in items if own != p and not own.is_relative_to(p)]
    moves, skipped, reserved = [], [], []
    for bundle, bucket in groups(items):
        unsafe = [p for p in bundle if any(m["kind"] in {"link", "special"} or rel.lower().endswith(PARTIAL_EXT)
                  for rel, m in before.items() if rel == p.name or rel.startswith(p.name + "/"))]
        if unsafe:
            skipped.extend({"source": p.name, "reason": "bundle contains a link, special file or incomplete download"} for p in bundle)
            continue
        project, reason = project_match(bundle, profiles, args.read_documents)
        common = bucket or category(bundle[0], bundle[0].is_dir())
        if not bucket and not bundle[0].is_dir():
            common = topic_bucket(bundle[0], common, schema)
        base = Path(cfg["output"]) / ("Projects/" + project if project else "By Type") / common
        if bucket:
            # Allocate a unique common directory so saved HTML resource names stay unchanged.
            allocated = unique(root / base, reserved)
            reserved.append(allocated)
            base = allocated.relative_to(root)
        for p in bundle:
            destination = unique(root / base / p.name, reserved)
            reserved.append(destination)
            moves.append({"source": p.name, "destination": destination.relative_to(root).as_posix(),
                          "project": project, "reason": reason, "identity": before[p.name]})
    plan_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    plan = {"version": VERSION, "id": plan_id, "owner": cfg["id"], "root": str(root),
            "moves": moves, "skipped": skipped, "before": before}
    path = folder / f"plan-{plan_id}.json"
    save_json(path, plan, exclusive=True)
    csv_path = path.with_suffix(".csv")
    with csv_path.open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "destination", "project", "reason"])
        writer.writeheader()
        for move in moves:
            row = {k: move[k] or "" for k in writer.fieldnames}
            # CSV spreadsheet formula injection can originate from filenames.
            writer.writerow({k: "'" + v if v.startswith(("=", "+", "-", "@")) else v for k, v in row.items()})
    save_json(folder / "latest-plan.json", {"file": path.name})
    counts = collections.Counter(m["project"] or "By Type" for m in moves)
    print(json.dumps({"plan": str(path), "preview_csv": str(csv_path), "moves": len(moves),
                      "skipped": skipped, "protected_names": sorted(keep_names), "destinations": counts}, ensure_ascii=False, indent=2))


def topic_bucket(path, default, schema):
    """Apply locally reviewed subject rules without changing project attribution."""
    matches = []
    vocabulary = terms(path.stem)
    for rule in schema.get("topics", []):
        name = rule.get("folder", "")
        if not name or label(name) != name or "/" in name or "\\" in name:
            raise SafetyError("Topic folder must be one ordinary folder name.")
        extensions = rule.get("extensions", [])
        if extensions and path.suffix.casefold() not in {e.casefold() for e in extensions}:
            continue
        wanted = set(rule.get("terms", []))
        threshold = int(rule.get("minimum_matches", 2))
        if threshold < 1 or not wanted:
            raise SafetyError("Topic rules need evidence terms and a positive threshold.")
        score = len(vocabulary & wanted)
        if score >= threshold:
            matches.append((score, name))
    matches.sort(reverse=True)
    if matches and (len(matches) == 1 or matches[0][0] > matches[1][0]):
        return default.split("/")[0] + "/" + matches[0][1]
    return default


def no_replace(source, destination):
    """Native atomic rename that refuses overwrites. Fail closed on unsupported hosts."""
    if os.name == "nt":
        os.rename(source, destination)  # Windows rename fails if destination exists.
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        fn = libc.renameat2
        fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        code = fn(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    elif sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        fn = libc.renamex_np
        fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        code = fn(os.fsencode(source), os.fsencode(destination), 4)
    else:
        raise SafetyError("This system has no supported atomic rename without overwrite.")
    if code:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), str(destination))


def journal_append(path, record):
    if (path.exists() or path.is_symlink()) and is_link(path):
        raise SafetyError("Journal must not be a link.")
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def load_run(root, folder, cfg, plan_value=None):
    value = plan_value or read_json(folder / "latest-plan.json")["file"]
    path = Path(value)
    if not path.is_absolute():
        path = folder / path
    if path.parent.resolve() != folder.resolve() or is_link(path):
        raise SafetyError("Plans must be stored directly inside this target's private state folder.")
    plan = read_json(path)
    if plan.get("root") != str(root) or plan.get("owner") != cfg["id"]:
        raise SafetyError("Plan belongs to a different folder or state.")
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[a-f0-9]{8}", plan.get("id", "")):
        raise SafetyError("Invalid plan identifier.")
    sources, destinations = set(), set()
    for move in plan["moves"]:
        src, dst = inside(root, move["source"]), inside(root, move["destination"])
        if len(Path(move["source"]).parts) != 1 or move["source"] in {STATE, cfg["output"], cfg["index"]}:
            raise SafetyError("Plan source must be an unmanaged direct child of the target.")
        if Path(move["destination"]).parts[0] != cfg["output"]:
            raise SafetyError("Plan destination must be inside the managed output folder.")
        if src == dst or dst.is_relative_to(src):
            raise SafetyError("Invalid self-containing move.")
        if str(src).casefold() in sources or str(dst).casefold() in destinations:
            raise SafetyError("Duplicate source or destination in plan.")
        sources.add(str(src).casefold())
        destinations.add(str(dst).casefold())
    return plan, folder / f"journal-{plan['id']}.jsonl"


def journal_records(path):
    if not path.exists():
        return []
    if is_link(path):
        raise SafetyError("Journal must not be a link.")
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            raise SafetyError("Incomplete journal: preserve it and inspect before resuming.")
    return records


def positions(root, plan, records):
    """Recover an interrupted rename using identity, not just the completion record."""
    intents = {r["source"] for r in records if r["event"] == "intent"}
    positions = {}
    for move in plan["moves"]:
        src, dst = inside(root, move["source"]), inside(root, move["destination"])
        wanted = move["identity"]
        src_same = src.exists() and meta(src) == wanted
        dst_same = dst.exists() and meta(dst) == wanted
        if src_same:
            positions[move["source"]] = move["source"]
        elif move["source"] in intents and dst_same:
            positions[move["source"]] = move["destination"]
        else:
            raise SafetyError("Missing or changed item: " + move["source"])
    return positions


def expected_location(relative, mapping):
    first, sep, remainder = relative.partition("/")
    return mapping.get(first, first) + (sep + remainder if sep else "")


def check_inventory(root, plan, mapping):
    failures = []
    for relative, wanted in plan["before"].items():
        current = root / expected_location(relative, mapping)
        # Preserve links too; never follow them. They were excluded from moves.
        if not current.exists() and not current.is_symlink():
            failures.append({"path": relative, "problem": "missing"})
        elif meta(current) != wanted:
            failures.append({"path": relative, "problem": "identity, size or timestamp changed"})
    return failures


def lock(folder):
    path = folder / "operation.lock"
    try:
        f = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise SafetyError("An operation lock exists. Check for a running process before removing this tool-owned lock file.")
    f.write(str(os.getpid()))
    f.close()
    return path


def apply(args):
    root = root_path(args.target)
    folder, cfg = state(root)
    plan, journal = load_run(root, folder, cfg, args.plan)
    operation_lock = lock(folder)
    try:
        records = journal_records(journal)
        mapping = positions(root, plan, records)
        failures = check_inventory(root, plan, mapping)
        if failures:
            raise SafetyError("Preview is stale. Changed original items: " + json.dumps(failures[:5]))
        # Detect additions within planned folder bundles, which would otherwise move unseen files.
        now = snapshot(root, cfg)
        expected = {expected_location(p, mapping) for p in plan["before"]}
        moved_roots = set(mapping.values())
        additions = [p for p in now if p not in expected and any(p == r or p.startswith(r + "/") for r in moved_roots)]
        if additions:
            raise SafetyError("A folder bundle changed after preview; generate a new preview.")
        # Preflight every destination before the first move.
        for move in plan["moves"]:
            if mapping[move["source"]] != move["source"]:
                continue
            dst = inside(root, move["destination"])
            if dst.exists() or dst.is_symlink():
                raise SafetyError("Destination already exists; generate a new preview.")
        moved, errors = 0, []
        for move in plan["moves"]:
            if mapping[move["source"]] != move["source"]:
                continue
            src, dst = inside(root, move["source"]), inside(root, move["destination"])
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                inside(root, move["destination"])
                if src.stat().st_dev != dst.parent.stat().st_dev:
                    raise SafetyError("Source and destination must be on the same filesystem.")
                if meta(src) != move["identity"]:
                    raise SafetyError("Source changed after preview.")
                journal_append(journal, {"event": "intent", **move})
                no_replace(src, dst)
                journal_append(journal, {"event": "done", **move})
                moved += 1
            except OSError as exc:
                errors.append({"source": move["source"], "error": str(exc)})
                journal_append(journal, {"event": "error", "source": move["source"], "error": str(exc)})
        mapping = positions(root, plan, journal_records(journal))
        failures = check_inventory(root, plan, mapping)
        report = {"moved_this_call": moved, "at_destination": sum(k != v for k, v in mapping.items()),
                  "left_at_source": [k for k, v in mapping.items() if k == v],
                  "errors": errors, "verification_failures": failures, "journal": journal.name}
        save_json(folder / f"result-{plan['id']}.json", report)
        make_index(root, cfg)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if failures or errors:
            return 2
    finally:
        operation_lock.unlink()  # Only this tool's own temporary lock; no original items deleted.
    return 0


def verify(args):
    root = root_path(args.target)
    folder, cfg = state(root)
    plan, journal = load_run(root, folder, cfg, args.plan)
    mapping = positions(root, plan, journal_records(journal))
    failures = check_inventory(root, plan, mapping)
    print(json.dumps({"original_items_checked": len(plan["before"]), "failures": failures,
                      "at_destination": sum(k != v for k, v in mapping.items()),
                      "at_source": sum(k == v for k, v in mapping.items())}, indent=2))
    return 2 if failures else 0


def undo(args):
    root = root_path(args.target)
    folder, cfg = state(root)
    plan, journal = load_run(root, folder, cfg, args.plan)
    operation_lock = lock(folder)
    try:
        mapping = positions(root, plan, journal_records(journal))
        if check_inventory(root, plan, mapping):
            raise SafetyError("Original items changed; undo refused. Preserve the journal for manual recovery.")
        for move in plan["moves"]:
            if mapping[move["source"]] != move["source"] and (root / move["source"]).exists():
                raise SafetyError("An original location is occupied; undo will not overwrite it.")
        restored = 0
        for move in reversed(plan["moves"]):
            if mapping[move["source"]] == move["source"]:
                continue
            src, dst = inside(root, move["destination"]), inside(root, move["source"])
            journal_append(journal, {"event": "undo_intent", **move})
            no_replace(src, dst)
            journal_append(journal, {"event": "undone", **move})
            restored += 1
        make_index(root, cfg)
        print(json.dumps({"restored": restored, "failures": check_inventory(root, plan, {})}, indent=2))
    finally:
        operation_lock.unlink()
    return 0


def validate_index(root, cfg):
    index = inside(root, cfg["index"])
    if not index.is_file() or any(meta(index)[k] != v for k, v in cfg["index_identity"].items()):
        raise SafetyError("The tool-owned index was replaced; refusing to overwrite it.")
    return index


def make_index(root, cfg):
    index = validate_index(root, cfg)
    output = inside(root, cfg["output"])
    bundles = set()
    imported = root / STATE / "restored-bundles.json"
    if imported.exists():
        for record in read_json(imported):
            path = inside(root, record["path"])
            if path.is_relative_to(output) and path.exists() and meta(path) == record["identity"]:
                bundles.add(path)
    for journal in (root / STATE).glob("journal-*.jsonl"):
        for record in journal_records(journal):
            if record.get("event") == "intent" and record.get("identity", {}).get("kind") == "dir":
                path = inside(root, record["destination"])
                if path.exists() and meta(path) == record["identity"]:
                    bundles.add(path)
    rows, folder_rows = [], []
    dates_path = root / STATE / "preserved-dates.json"
    dates = read_json(dates_path) if dates_path.exists() else {}
    def entry(p, directory=False):
        rel = p.relative_to(root).as_posix()
        st = p.stat()
        parts = Path(rel).parts
        project = parts[2] if len(parts) > 2 and parts[0] == cfg["output"] and parts[1] == "Projects" else "By Type"
        created = getattr(st, "st_birthtime_ns", None)
        saved = dates.get(rel)
        if saved and saved.get("size") == st.st_size and saved.get("mtime_ns") == st.st_mtime_ns:
            created = saved.get("created_ns")
        return {"name": p.name, "path": rel, "url": quote(rel, safe="/"), "project": project,
                "folder": directory, "size": 0 if directory else st.st_size,
                "modified": st.st_mtime_ns // 1_000_000,
                "created": created // 1_000_000 if created is not None else None,
                "kind": "Folder" if directory else p.suffix.lstrip(".").upper() or "FILE"}
    def visit(folder):
        for p in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
            if is_link(p):
                continue
            rel = p.relative_to(root).as_posix()
            if p.is_dir():
                if p in bundles:
                    folder_rows.append(entry(p, True))
                visit(p)
            else:
                rows.append(entry(p))
    if output.exists():
        visit(output)
    for p in sorted(root.iterdir()):
        if p.name in {STATE, cfg["output"], cfg["index"]} or is_link(p):
            continue
        if p.is_dir():
            folder_rows.append(entry(p, True)); visit(p)
        else:
            rows.append(entry(p))
    for folder_row in folder_rows:
        prefix = folder_row["path"] + "/"
        folder_row["size"] = sum(row["size"] for row in rows if row["path"].startswith(prefix))
    payload = json.dumps({"files": rows, "bundles": folder_rows}, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    page = Path(__file__).with_name("library.html").read_text(encoding="utf-8").replace("__FILE_DATA__", payload)
    index.write_text(page, encoding="utf-8")
    return index


def index(args):
    root = root_path(args.target)
    _, cfg = state(root)
    print(make_index(root, cfg))


def main(argv=None):
    configure_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, fn in [("learn", learn), ("preview", preview), ("apply", apply),
                     ("verify", verify), ("undo", undo), ("index", index)]:
        cmd = commands.add_parser(name)
        cmd.add_argument("--target", required=True, help="Existing folder to organize; all moves remain inside it")
        cmd.set_defaults(fn=fn)
        if name == "learn":
            cmd.add_argument("--project", action="append", default=[], help="One actual reference project folder; repeat for more")
            cmd.add_argument("--container", action="append", default=[], help="Explicit container whose immediate folders are projects")
            cmd.add_argument("--read-documents", action="store_true", help="Opt into bounded local document text sampling")
        if name == "preview":
            cmd.add_argument("--keep", action="append", default=[], help="Leave this exact top-level filename or folder untouched")
            cmd.add_argument("--types-only", action="store_true", help="Skip project matching")
            cmd.add_argument("--read-documents", action="store_true", help="Opt into bounded local document text matching")
        if name in {"apply", "verify", "undo"}:
            cmd.add_argument("--plan", help="Plan filename in private state; defaults to latest preview")
    args = parser.parse_args(argv)
    try:
        return args.fn(args) or 0
    except (SafetyError, OSError, ValueError, KeyError) as exc:
        print(f"Stopped safely: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
