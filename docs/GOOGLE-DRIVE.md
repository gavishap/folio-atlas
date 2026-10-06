# Optional Google Drive archive

Invoke Folio Archive explicitly. Sorting and Refresh never trigger an upload or deletion.

## 1. Build outside the source

Choose an outside-target working folder with room for the ZIP, the downloaded ZIP, and a restored copy. Keep its receipts and `.folio-atlas-receipt-key` private and together. They survive cleanup. Your personal archive contains your files and schema; it is not the public plugin package.

```text
python scripts/folio.py backup build --target TARGET --out WORK
```

The result names the archive/build receipt and records its complete SHA256. Files are verified inside the archive independently of writing them. Links are recorded but their external targets are not included.

## 2. Upload and download the actual cloud object

The agent inspects available connector operations. Use a Google Drive connector/plugin if it supports binary upload and download at the archive's size. Otherwise use approved computer-use browser controls or manually upload the ZIP. No account connection is mandatory or bundled; follow the relevant tool's authentication and permissions flow.

Record the actual observed Drive URL and upload completion. Download that object to a distinct completed ZIP. A copy of the original local ZIP is not proof of a cloud transfer. Never proceed with a partial browser download or bypass a security block. Inspect existing progress before starting another download. The Python engine does not upload/download or assert where a supplied file came from.

## 3. Verify the full roundtrip

```text
python scripts/folio.py backup verify-roundtrip --build BUILD_RECEIPT --downloaded ACTUAL_CLOUD_ZIP --restore-to NEW_RESTORE_FOLDER --cloud-url OBSERVED_DRIVE_URL
```

The ZIP size and full SHA256 must match. The destination must not exist and must be outside the source. Every regular file is extracted and hashed, reread and checked, and matched against the exact inventory. Empty directories are included. If START HERE is present, its local relative links and date/size records are checked. Require `complete=true` and review every result.

Keep originals if anything fails. A partial restore cannot be retried in place; inspect it and choose a separately named new folder. Never execute helpers from a downloaded archive. Use this trusted package's engine.

## 4. Clean up only the requested scope

After explicit user instruction, inspect the remote object again to confirm it still exists. Then create a concrete signed preview:

```text
python scripts/folio.py backup cleanup-preview --receipt ROUNDTRIP_RECEIPT --scope copies --keep EXACT_PROTECTED_NAME
```

Scopes are **copies** (temporary original ZIP, actual downloaded ZIP, and verified restored copy), **originals** (manifest-covered original regular files), or **all**. Review file count, bytes, and preserved items. Protected names repeat and are exact root filenames/folder names. Nothing is deleted by preview.

```text
python scripts/folio.py backup cleanup --plan SIGNED_PLAN --confirm PLAN_ID --cloud-available
```

For separately authorized original deletion, preview `--scope originals` or `all` and add `--delete-originals` to execution. “Delete the backup” means copies, not originals. If user intent is ambiguous, obtain that scope before execution. `--cloud-available` is the agent's attestation of its fresh remote check; Python has no remote API. A proof older than 24 hours requires a new genuine download/verification.

New, edited, unbacked, protected, linked, and locked content stays. Only verified regular files and empty verified directories are removed. The source folder, organizer schema/journals, index, external receipt evidence, and **Google Drive object** stay. Final receipts list bytes removed and preserved entries. Report failures/remaining files accurately.

## 5. Open it on another computer

Clone this public tool, download your private archive, and restore to a new folder:

```text
python scripts/folio.py backup restore --archive YOUR_DOWNLOADED_ZIP --destination NEW_FOLDER
```

Open `NEW_FOLDER/START HERE - Folio Atlas.html` locally. Relative links work with its restored files; size/date views use preserved metadata. The restore rebinds ownership so future Refresh works on this machine. Old undo history is read-only after relocation. New refresh runs are still undoable.

You can also extract `Library/` with a ZIP tool and browse the existing HTML, but use `backup restore` before asking Folio to refresh a relocated library. Keep the entire directory layout; Google Drive's web HTML preview is not the local browser.
