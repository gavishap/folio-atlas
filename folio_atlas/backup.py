"""Opt-in, manifest-verified backups and explicitly authorized local cleanup.

No cloud credentials or upload code live here. The agent uses an available Drive
connector, browser, or an authenticated transfer client, then supplies its download.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
from html.parser import HTMLParser
import json
import os
import re
from pathlib import Path, PurePosixPath
import secrets
import stat
import sys
from urllib.parse import urlsplit, unquote
import uuid
import zipfile
from . import organizer as org

MANIFEST = "__FOLIO_ATLAS__/manifest.json"
PAYLOAD = "Library/"


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def check_ancestors(path):
    for parent in [path, *path.parents]:
        if (parent.exists() or parent.is_symlink()) and org.is_link(parent):
            raise org.SafetyError("A path contains a link or junction: " + str(parent))


def ordinary(value, directory=False, missing=False):
    path = Path(value).expanduser().absolute()
    check_ancestors(path)
    path = path.resolve(strict=not missing)
    if directory and (path == Path(path.anchor) or path == Path.home().resolve()):
        raise org.SafetyError("Choose a named working folder, never a drive root or home.")
    if path.exists() and (not path.is_dir() if directory else not path.is_file()):
        raise org.SafetyError("Unexpected filesystem entry: " + str(path))
    return path


def relative(value):
    p = PurePosixPath(value)
    if (not value or p.is_absolute() or any(x in {".", "..", ""} for x in value.split("/"))
            or "\\" in value or ":" in value or "\x00" in value):
        raise org.SafetyError("Unsafe or nonportable archive path.")
    # Folder labels are deliberately short; real filenames can be longer.
    # Validate Windows portability without rewriting or truncating originals.
    if any(re.search(r'[<>:"\\|?*\x00-\x1f]', x) or x.endswith((" ", "."))
           or re.match(r'(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', x)
           or len(x.encode("utf-16-le")) > 510 for x in p.parts):
        raise org.SafetyError("Archive name cannot be safely restored on Windows.")
    return p


def snap(path):
    check_ancestors(path)
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) and not stat.S_ISDIR(s.st_mode):
        raise org.SafetyError("Unexpected special file.")
    return {"path": str(path), "dev": s.st_dev, "ino": s.st_ino,
            "size": s.st_size if stat.S_ISREG(s.st_mode) else 0,
            "mtime_ns": s.st_mtime_ns, "created_ns": getattr(s, "st_birthtime_ns", None)}


def stable_hash(path):
    before = snap(path)
    value = org.digest(path)
    if before != snap(path):
        raise org.SafetyError("File changed while being verified: " + str(path))
    return value


def inventory(root):
    files, directories, links = [], [], []
    todo = [root]
    while todo:
        base = todo.pop()
        for path in sorted(base.iterdir(), key=lambda p: p.name.casefold()):
            rel = path.relative_to(root).as_posix()
            relative(rel)
            if org.is_link(path):
                links.append({"path": rel, "target": os.readlink(path)})
            elif path.is_dir():
                directories.append({**snap(path), "path": rel})
                todo.append(path)
            elif path.is_file():
                files.append({**snap(path), "path": rel})
            else:
                raise org.SafetyError("Special files cannot be backed up safely: " + rel)
    return files, directories, links


def key_path(parent):
    return parent / ".folio-atlas-receipt-key"


def get_key(parent, create=False):
    path = key_path(parent)
    check_ancestors(path)
    if not path.exists() and create:
        with path.open("xb") as f:
            f.write(secrets.token_bytes(32))
        if os.name != "nt":
            path.chmod(0o600)
    value = path.read_bytes()
    if len(value) != 32:
        raise org.SafetyError("Invalid local verification key.")
    return value


def seal(path, data, create=False):
    data = dict(data)
    data["signature"] = hmac.new(get_key(path.parent, create), canonical(data), hashlib.sha256).hexdigest()
    org.save_json(path, data, exclusive=True)
    return path


def unseal(value):
    path = ordinary(value)
    data = org.read_json(path)
    signature = data.pop("signature", None)
    expected = hmac.new(get_key(path.parent), canonical(data), hashlib.sha256).hexdigest()
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
        raise org.SafetyError("Receipt or cleanup plan was modified; nothing may be deleted.")
    return path, data


def load_archive(archive, expected_manifest=None):
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        names = [m.filename for m in members]
        if len({n.casefold() for n in names}) != len(names):
            raise org.SafetyError("Duplicate archive paths.")
        for member in members:
            relative(member.filename.rstrip("/"))
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}) or member.flag_bits & 1:
                raise org.SafetyError("Linked, special, or encrypted ZIP entry.")
        if z.getinfo(MANIFEST).file_size > 64 * 1024 * 1024:
            raise org.SafetyError("Manifest is unexpectedly large.")
        raw = z.read(MANIFEST)
        if expected_manifest and hashlib.sha256(raw).hexdigest() != expected_manifest:
            raise org.SafetyError("Embedded manifest differs from the recorded backup.")
        manifest = json.loads(raw)
        if manifest.get("format") != "folio-atlas-backup-1":
            raise org.SafetyError("Unsupported backup format.")
        all_rel = [r["path"] for r in manifest["files"] + manifest["directories"]]
        if len(set(x.casefold() for x in all_rel)) != len(all_rel):
            raise org.SafetyError("Duplicate manifest entries.")
        for rel in all_rel:
            relative(rel)
        expected = {MANIFEST, PAYLOAD}
        expected.update(PAYLOAD + r["path"] for r in manifest["files"])
        expected.update(PAYLOAD + r["path"] + "/" for r in manifest["directories"])
        if set(names) != expected:
            raise org.SafetyError("Archive contains missing or unexpected entries.")
        for record in manifest["files"]:
            if not isinstance(record["size"], int) or record["size"] < 0:
                raise org.SafetyError("Invalid recorded size.")
            if not isinstance(record["sha256"], str) or len(record["sha256"]) != 64:
                raise org.SafetyError("Invalid content hash.")
    return manifest


def build(args):
    root = org.root_path(args.target)
    out = ordinary(args.out, directory=True, missing=True)
    if out == root or out.is_relative_to(root):
        raise org.SafetyError("Put backup working files outside the source folder.")
    out.mkdir(parents=True, exist_ok=True)
    if (root / org.STATE).exists():
        _, cfg = org.state(root)
        if (root / org.STATE / "operation.lock").exists():
            raise org.SafetyError("An organization operation is running. Finish it before backing up.")
        org.make_index(root, cfg)
    files, directories, links = inventory(root)
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    archive = out / ("folio-atlas-" + run + ".zip")
    manifest = {"format": "folio-atlas-backup-1", "created_utc": now(), "files": [],
                "directories": directories, "links_recorded_without_following": links}
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as z:
        z.writestr(PAYLOAD, b"")
        for record in directories:
            z.writestr(PAYLOAD + record["path"] + "/", b"")
        for record in files:
            path = root / record["path"]
            before = snap(path)
            h = hashlib.sha256()
            with path.open("rb") as source, z.open(PAYLOAD + record["path"], "w", force_zip64=True) as dest:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    h.update(chunk); dest.write(chunk)
            if before != snap(path):
                raise org.SafetyError("Source changed during backup; keep the originals.")
            manifest["files"].append({**record, "sha256": h.hexdigest()})
        after_files, after_dirs, after_links = inventory(root)
        if (files != after_files or {r['path'] for r in directories} != {r['path'] for r in after_dirs}
                or links != after_links):
            raise org.SafetyError("Source inventory changed during backup.")
        raw = canonical(manifest)
        z.writestr(MANIFEST, raw)
    load_archive(archive, hashlib.sha256(raw).hexdigest())
    # Reading each archived file detects archive corruption independently of the writer.
    with zipfile.ZipFile(archive) as z:
        for record in manifest["files"]:
            h = hashlib.sha256()
            with z.open(PAYLOAD + record["path"]) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
            if h.hexdigest() != record["sha256"]:
                raise org.SafetyError("Archive content verification failed.")
    report = {"kind": "folio-build", "complete": True, "created_utc": now(),
              "source_root": str(root), "source_root_identity": snap(root),
              "archive": str(archive), "archive_bytes": archive.stat().st_size,
              "archive_sha256": stable_hash(archive), "manifest_sha256": hashlib.sha256(raw).hexdigest(),
              "files": len(files), "directories": len(directories), "links_not_copied": len(links)}
    receipt = seal(out / ("build-" + run + ".json"), report, create=True)
    print(json.dumps({"archive": str(archive), "build_receipt": str(receipt),
                      "sha256": report["archive_sha256"], "files_verified": len(files),
                      "linked_entries_not_followed": len(links)}, indent=2))


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_data = False; self.parts = []; self.hrefs = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("id") == "file-data": self.in_data = True
        if tag == "a" and attrs.get("href"): self.hrefs.append(attrs["href"])
    def handle_endtag(self, tag):
        if tag == "script": self.in_data = False
    def handle_data(self, data):
        if self.in_data: self.parts.append(data)


def verify_index(library, manifest):
    owner = library / org.STATE / "owner.json"
    if not owner.is_file():
        return {"present": False, "links_checked": 0}
    cfg = org.read_json(owner)
    page = library / relative(cfg["index"])
    parser = PageParser(); parser.feed(page.read_text(encoding="utf-8"))
    data = json.loads("".join(parser.parts))
    expected = {r["path"]: r for r in manifest["files"]}
    checked = 0
    for entry in data["files"] + data["bundles"]:
        parsed = urlsplit(entry["url"])
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise org.SafetyError("Index contains a nonportable or incorrectly escaped file URL.")
        rel = unquote(parsed.path).rstrip("/")
        target = library / relative(rel)
        if not target.exists() or not target.resolve().is_relative_to(library):
            raise org.SafetyError("An index link does not resolve inside the restored library.")
        if not entry["folder"]:
            record = expected[rel]
            if entry["size"] != record["size"] or abs(entry["modified"] - record["mtime_ns"] / 1_000_000) > 1:
                raise org.SafetyError("Index date or size differs from the file manifest.")
        checked += 1
    return {"present": True, "links_checked": checked, "dates_and_sizes_match": True}


def verify_roundtrip(args):
    receipt_path, original = unseal(args.build)
    if original.get("kind") != "folio-build" or not original.get("complete"):
        raise org.SafetyError("A complete trusted build receipt is required.")
    downloaded = ordinary(args.downloaded)
    if downloaded.suffix.casefold() != ".zip":
        raise org.SafetyError("Wait for a completed ZIP, not a partial browser download.")
    archive = Path(original["archive"])
    if downloaded == archive or (archive.exists() and os.path.samefile(downloaded, archive)):
        raise org.SafetyError("The original local ZIP cannot prove a cloud roundtrip.")
    parsed = urlsplit(args.cloud_url)
    if parsed.scheme != "https" or parsed.hostname != "drive.google.com":
        raise org.SafetyError("Record the observed Google Drive file or folder URL.")
    if downloaded.stat().st_size != original["archive_bytes"] or stable_hash(downloaded) != original["archive_sha256"]:
        raise org.SafetyError("Downloaded bytes differ from the uploaded backup. Keep every original.")
    manifest = load_archive(downloaded, original["manifest_sha256"])
    destination = ordinary(args.restore_to, directory=True, missing=True)
    source_root = Path(original["source_root"])
    if destination.exists() or destination == source_root or destination.is_relative_to(source_root):
        raise org.SafetyError("Restore into a NEW empty working folder outside the source.")
    if receipt_path.parent == destination or receipt_path.parent.is_relative_to(destination):
        raise org.SafetyError("Verification receipts must survive deletion of the restored copy.")
    destination.mkdir(parents=True, exist_ok=False)
    library = destination / "Library"; library.mkdir()
    with zipfile.ZipFile(downloaded) as z:
        for record in sorted(manifest["directories"], key=lambda r: len(PurePosixPath(r["path"]).parts)):
            target = library / relative(record["path"])
            check_ancestors(target)
            target.mkdir(parents=True, exist_ok=True)
        for record in manifest["files"]:
            target = library / relative(record["path"])
            check_ancestors(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256(); total = 0
            with z.open(PAYLOAD + record["path"]) as src, target.open("xb") as dst:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    total += len(chunk); h.update(chunk); dst.write(chunk)
            if total != record["size"] or h.hexdigest() != record["sha256"]:
                raise org.SafetyError("Restoration failed file verification. Keep all local originals.")
            os.utime(target, ns=(record["mtime_ns"], record["mtime_ns"]))
    actual_files, actual_dirs, actual_links = inventory(library)
    if actual_links or {r["path"] for r in actual_files} != {r["path"] for r in manifest["files"]}:
        raise org.SafetyError("Restored file inventory mismatch.")
    if {r["path"] for r in actual_dirs} != {r["path"] for r in manifest["directories"]}:
        raise org.SafetyError("Restored directory inventory mismatch.")
    verified_files = []
    expected = {r["path"]: r for r in manifest["files"]}
    for record in actual_files:
        path = library / record["path"]
        value = stable_hash(path)
        if value != expected[record["path"]]["sha256"]:
            raise org.SafetyError("Restored file changed before verification completed.")
        verified_files.append({**snap(path), "sha256": value})
    index_result = verify_index(library, manifest)
    proof = {"kind": "folio-roundtrip", "complete": True, "verified_utc": now(),
             "cloud_url": args.cloud_url, "source_root": original["source_root"],
             "source_root_identity": original["source_root_identity"],
             "archive": original["archive"], "downloaded_archive": str(downloaded),
             "archive_sha256": original["archive_sha256"], "archive_bytes": original["archive_bytes"],
             "manifest_sha256": original["manifest_sha256"], "manifest": manifest,
             "restore_root": str(destination), "restore_files": verified_files,
             "restore_directories": [snap(library / r["path"]) for r in actual_dirs] + [snap(library), snap(destination)],
             "index": index_result, "files_verified": len(verified_files)}
    proof_path = seal(receipt_path.parent / ("roundtrip-" + uuid.uuid4().hex[:12] + ".json"), proof)
    print(json.dumps({"complete": True, "roundtrip_receipt": str(proof_path),
                      "restored_library": str(library), "files_verified": len(verified_files),
                      "index": index_result, "cloud_url": args.cloud_url}, indent=2))


def cleanup_preview(args):
    if any(not name or len(relative(name).parts) != 1 for name in args.keep):
        raise org.SafetyError("Protected names must be exact direct-child filenames or folder names.")
    receipt_path, proof = unseal(args.receipt)
    if proof.get("kind") != "folio-roundtrip" or not proof.get("complete"):
        raise org.SafetyError("Only a successful full cloud roundtrip permits cleanup.")
    if (datetime.now(timezone.utc) - datetime.fromisoformat(proof["verified_utc"])).total_seconds() > 24 * 3600:
        raise org.SafetyError("Verification is older than 24 hours. Verify a fresh cloud download first.")
    source = ordinary(proof["source_root"], directory=True)
    if any(snap(source)[k] != proof["source_root_identity"][k] for k in ("dev", "ino")):
        raise org.SafetyError("The original source folder was replaced.")
    scope = args.scope
    allowed, dirs, preserved = [], [], []
    roots = [source, Path(proof["restore_root"])]
    protected = set(args.keep) | {org.STATE}
    owner = source / org.STATE / "owner.json"
    if owner.exists():
        protected.add(org.read_json(owner)["index"])
        schema = source / org.STATE / "schema.json"
        if schema.exists():
            names = org.read_json(schema).get("keep_names", [])
            if any(not name or len(relative(name).parts) != 1 for name in names):
                raise org.SafetyError("Saved protected names must be direct-child names.")
            protected.update(names)
    def approve(path, wanted, category):
        if not path.exists() and not path.is_symlink(): return
        if category == "verified_original" and path.name.casefold().endswith(org.PARTIAL_EXT):
            preserved.append({"path": str(path), "reason": "incomplete download kept unconditionally"}); return
        if path.is_relative_to(source) and path.relative_to(source).parts[0] in protected:
            preserved.append({"path": str(path), "reason": "explicitly protected"}); return
        try:
            if path.is_symlink() or path.stat().st_size != wanted["size"] or stable_hash(path) != wanted["sha256"]:
                preserved.append({"path": str(path), "reason": "new, changed, or linked content"}); return
            allowed.append({**snap(path), "sha256": wanted["sha256"], "category": category})
        except (org.SafetyError, OSError) as exc:
            preserved.append({"path": str(path), "reason": str(exc)})
    if scope in {"copies", "all"}:
        for name in ("archive", "downloaded_archive"):
            approve(Path(proof[name]), {"size": proof["archive_bytes"], "sha256": proof["archive_sha256"]}, "verified_backup_copy")
        for record in proof["restore_files"]:
            approve(Path(record["path"]), record, "verified_restored_copy")
        for record in proof["restore_directories"]:
            path = Path(record["path"])
            if path.exists() and not org.is_link(path):
                current = snap(path)
                if all(current[k] == record[k] for k in ("dev", "ino")): dirs.append(current)
                else: preserved.append({"path": str(path), "reason": "restored directory was replaced"})
        restore_root = Path(proof["restore_root"])
        if restore_root.exists():
            known = {r["path"] for r in proof["restore_files"]}
            current_files, _, current_links = inventory(restore_root)
            preserved.extend({"path": str(restore_root / r["path"]), "reason": "added to restored copy after verification"}
                             for r in current_files if str(restore_root / r["path"]) not in known)
            preserved.extend({"path": str(restore_root / r["path"]), "reason": "new link kept"} for r in current_links)
    if scope in {"originals", "all"}:
        for record in proof["manifest"]["files"]:
            if PurePosixPath(record["path"]).parts[0] in protected: continue
            approve(source / relative(record["path"]), record, "verified_original")
        for record in proof["manifest"]["directories"]:
            if PurePosixPath(record["path"]).parts[0] in protected: continue
            path = source / relative(record["path"])
            if path.exists() and not org.is_link(path):
                current = snap(path)
                if all(current[k] == record[k] for k in ("dev", "ino")): dirs.append(current)
                else: preserved.append({"path": str(path), "reason": "original directory was replaced"})
        current, _, links = inventory(source)
        expected = {r["path"] for r in proof["manifest"]["files"]}
        for record in current:
            if record["path"] not in expected:
                preserved.append({"path": str(source / record["path"]), "reason": "added after the verified backup"})
        preserved.extend({"path": str(source / r["path"]), "reason": "link retained; external target never backed up"} for r in links)
    if len({r['path'].casefold() for r in allowed}) != len(allowed):
        raise org.SafetyError("Overlapping cleanup artifacts.")
    run = uuid.uuid4().hex[:12]
    plan = {"kind": "folio-cleanup", "id": run, "created_utc": now(), "scope": scope,
            "receipt": str(receipt_path), "source_root": str(source),
            "restore_root": proof["restore_root"], "archive_paths": [proof["archive"], proof["downloaded_archive"]],
            "files": allowed, "directories": sorted(dirs, key=lambda r: -len(Path(r["path"]).parts)),
            "protected_names": sorted(protected), "preserved_items": preserved,
            "protected_file_hashes": [{"name": name, "sha256": stable_hash(source / name)}
                                      for name in sorted(protected - {org.STATE, org.read_json(owner)["index"] if owner.exists() else ""})
                                      if (source / name).is_file() and not org.is_link(source / name)],
            "cloud_url": proof["cloud_url"]}
    plan_path = seal(receipt_path.parent / ("cleanup-plan-" + run + ".json"), plan)
    print(json.dumps({"plan": str(plan_path), "confirmation_id": run, "scope": scope,
                      "files": len(allowed), "bytes": sum(r["size"] for r in allowed),
                      "preserved": preserved, "originals_will_be_deleted": scope in {"originals", "all"}}, indent=2))


def cleanup(args):
    plan_path, plan = unseal(args.plan)
    if plan.get("kind") != "folio-cleanup" or args.confirm != plan["id"]:
        raise org.SafetyError("Use the exact reviewed plan and its confirmation identifier.")
    _, proof = unseal(plan["receipt"])
    if not proof.get("complete") or proof.get("kind") != "folio-roundtrip":
        raise org.SafetyError("Full restoration verification is required.")
    if (datetime.now(timezone.utc) - datetime.fromisoformat(proof["verified_utc"])).total_seconds() > 24 * 3600:
        raise org.SafetyError("Cloud verification expired. Download and verify it again.")
    if not args.cloud_available:
        raise org.SafetyError("The agent must first confirm the verified backup still exists in Google Drive.")
    if plan["scope"] in {"originals", "all"} and not args.delete_originals:
        raise org.SafetyError("Deleting originals requires separate explicit authorization.")
    source = ordinary(plan["source_root"], directory=True)
    if any(snap(source)[k] != proof["source_root_identity"][k] for k in ("dev", "ino")):
        raise org.SafetyError("Original source folder was replaced after verification.")
    restore = ordinary(plan["restore_root"], directory=True, missing=True)
    artifacts = {str(Path(p)) for p in plan["archive_paths"]}
    def checked(value, directory=False):
        path = Path(value).absolute()
        check_ancestors(path)
        if path == source or path == Path(path.anchor) or path == Path.home().resolve():
            raise org.SafetyError("Never delete the source folder, home, or drive root.")
        in_source = path.is_relative_to(source)
        in_restore = path == restore or path.is_relative_to(restore)
        if not in_source and not in_restore and str(path) not in artifacts:
            raise org.SafetyError("Cleanup path is outside verified scope.")
        if directory and not in_source and not in_restore:
            raise org.SafetyError("Artifact parent directories are never cleanup targets.")
        if in_source and path.relative_to(source).parts[0] in plan["protected_names"]:
            raise org.SafetyError("Protected item appears in a cleanup plan.")
        return path
    # Validate the whole scope before deleting the first entry.
    for record in plan["files"]: checked(record["path"])
    for record in plan["directories"]: checked(record["path"], True)
    for record in plan.get("protected_file_hashes", []):
        path = source / record["name"]
        if stable_hash(path) != record["sha256"]:
            raise org.SafetyError("A protected file changed since the cleanup preview.")
    deleted, kept = [], list(plan["preserved_items"])
    journal = plan_path.parent / ("cleanup-journal-" + plan["id"] + ".jsonl")
    if journal.exists():
        raise org.SafetyError("Cleanup was already attempted. Review its journal before creating another plan.")
    with journal.open("x", encoding="utf-8") as log:
        for record in plan["files"]:
            path = checked(record["path"])
            if not path.exists(): continue
            try:
                if record["category"] == "verified_original" and path.name.casefold().endswith(org.PARTIAL_EXT):
                    raise org.SafetyError("Incomplete download kept unconditionally.")
                current = snap(path)
                if any(current[k] != record[k] for k in ("dev", "ino", "size", "mtime_ns")) or stable_hash(path) != record["sha256"]:
                    raise org.SafetyError("Contents changed after the preview; preserved.")
                log.write(json.dumps({"intent": str(path), "sha256": record["sha256"]}) + "\n"); log.flush(); os.fsync(log.fileno())
                path.unlink()  # Exactly one verified regular file. Never recursive deletion.
                deleted.append({"path": str(path), "bytes": record["size"]})
                log.write(json.dumps({"deleted": str(path), "bytes": record["size"]}) + "\n"); log.flush()
            except (org.SafetyError, OSError) as exc:
                kept.append({"path": str(path), "reason": str(exc)})
        for record in plan["directories"]:
            try:
                path = checked(record["path"], True)
                if not path.exists(): continue
                current = snap(path)
                if any(current[k] != record[k] for k in ("dev", "ino")): continue
                path.rmdir()  # Empty only; new or changed content protects every parent.
                log.write(json.dumps({"empty_directory_removed": str(path)}) + "\n")
            except (org.SafetyError, OSError) as exc:
                kept.append({"path": record["path"], "reason": "directory retained: " + str(exc)})
    if (source / org.STATE / "owner.json").exists():
        _, cfg = org.state(source); org.make_index(source, cfg)
    report = {"kind": "folio-cleanup-result", "complete": True, "finished_utc": now(),
              "files_deleted": len(deleted), "bytes_deleted": sum(r["bytes"] for r in deleted),
              "deleted_items": deleted, "preserved_items": kept, "cloud_unchanged": True,
              "cloud_url": plan["cloud_url"], "scope": plan["scope"], "journal": str(journal),
              "remaining_source_entries": sorted(p.name for p in source.iterdir()),
              "restored_copy_still_present": restore.exists(),
              "protected_files": [{"name": r["name"], "sha256": stable_hash(source / r["name"]),
                                   "unchanged": stable_hash(source / r["name"]) == r["sha256"]}
                                  for r in plan.get("protected_file_hashes", [])]}
    result = seal(plan_path.parent / ("cleanup-result-" + plan["id"] + ".json"), report)
    print(json.dumps({"files_deleted": report["files_deleted"], "bytes_deleted": report["bytes_deleted"],
                      "preserved": kept, "receipt": str(result), "cloud_unchanged": True}, indent=2))


def restore(args):
    # Restoring elsewhere needs no cloud or local-deletion authorization.
    archive = ordinary(args.archive)
    manifest = load_archive(archive)
    destination = ordinary(args.destination, directory=True, missing=True)
    if destination.exists(): raise org.SafetyError("Restore destination must not already exist.")
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        for r in sorted(manifest["directories"], key=lambda r: len(PurePosixPath(r["path"]).parts)):
            (destination / relative(r["path"])).mkdir(parents=True, exist_ok=True)
        for r in manifest["files"]:
            path = destination / relative(r["path"])
            check_ancestors(path); path.parent.mkdir(parents=True, exist_ok=True)
            with z.open(PAYLOAD + r["path"]) as src, path.open("xb") as dst:
                for chunk in iter(lambda: src.read(1024 * 1024), b""): dst.write(chunk)
            if stable_hash(path) != r["sha256"] or path.stat().st_size != r["size"]:
                raise org.SafetyError("Restored file failed verification.")
            os.utime(path, ns=(r["mtime_ns"], r["mtime_ns"]))
    index_result = verify_index(destination, manifest)
    # Rebind only owned runtime metadata after verifying the untouched restoration.
    owner = destination / org.STATE / "owner.json"
    if owner.exists():
        cfg = org.read_json(owner)
        if cfg.get("tool") != "folio-atlas": raise org.SafetyError("Unexpected runtime owner.")
        index = destination / relative(cfg["index"])
        page = PageParser(); page.feed(index.read_text(encoding="utf-8"))
        bundle_data = json.loads("".join(page.parts))["bundles"]
        rebound_bundles = []
        for entry in bundle_data:
            bundle = destination / relative(entry["path"])
            if bundle.is_dir():
                rebound_bundles.append({"path": entry["path"], "identity": org.meta(bundle)})
        cfg.update(root=str(destination), id=uuid.uuid4().hex,
                   index_identity={k: org.meta(index)[k] for k in ("dev", "ino")},
                   imported_history_is_read_only=True)
        org.save_json(owner, cfg)
        org.save_json(destination / org.STATE / "restored-bundles.json", rebound_bundles)
        org.save_json(destination / org.STATE / "preserved-dates.json",
                      {r["path"]: {k: r[k] for k in ("size", "mtime_ns", "created_ns")} for r in manifest["files"]})
    print(json.dumps({"complete": True, "restored_folder": str(destination), "files_verified": len(manifest["files"]),
                      "index": index_result, "refresh_ready": owner.exists(), "old_undo_history": "read-only after relocation"}, indent=2))


def main(argv=None):
    org.configure_output()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("build"); p.add_argument("--target", required=True); p.add_argument("--out", required=True); p.set_defaults(fn=build)
    p = commands.add_parser("verify-roundtrip"); p.add_argument("--build", required=True); p.add_argument("--downloaded", required=True); p.add_argument("--restore-to", required=True); p.add_argument("--cloud-url", required=True); p.set_defaults(fn=verify_roundtrip)
    p = commands.add_parser("restore"); p.add_argument("--archive", required=True); p.add_argument("--destination", required=True); p.set_defaults(fn=restore)
    p = commands.add_parser("cleanup-preview"); p.add_argument("--receipt", required=True); p.add_argument("--scope", choices=["copies", "originals", "all"], default="copies"); p.add_argument("--keep", action="append", default=[]); p.set_defaults(fn=cleanup_preview)
    p = commands.add_parser("cleanup"); p.add_argument("--plan", required=True); p.add_argument("--confirm", required=True); p.add_argument("--delete-originals", action="store_true"); p.add_argument("--cloud-available", action="store_true"); p.set_defaults(fn=cleanup)
    args = parser.parse_args(argv)
    try: return args.fn(args) or 0
    except (org.SafetyError, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print("Stopped safely: " + str(exc), file=sys.stderr); return 2
