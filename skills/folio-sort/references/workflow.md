# Sorting and recovery

Use these arguments with `python scripts/folio.py` from the package root:

```text
learn   --target TARGET --project PROJECT [--project ANOTHER]
learn   --target TARGET --container PROJECT_CONTAINER
preview --target TARGET [--keep EXACT_NAME] [--read-documents]
preview --target TARGET --types-only
apply   --target TARGET --plan PLAN_FILENAME
verify  --target TARGET --plan PLAN_FILENAME
index   --target TARGET
undo    --target TARGET --plan PLAN_FILENAME
```

Use explicit plan filenames from emitted JSON, not a changing latest pointer. Learn samples up to 300 eligible filenames per project, excludes common dependency/system directories, and records a bounded set of document SHA256 fingerprints. With `--read-documents`, supported text and Office XML are sampled locally; PDFs additionally need optional `pypdf`. Unsupported or unreadable documents fall back to filename evidence.

Project evidence is a distinctive name/alias, exact eligible document fingerprint, reviewed multiword content phrase, or several distinct learned terms. The winning score must meet a threshold and beat the next candidate. Shared terms are removed during learning. No embedding service, pretrained personal profile, or model API is used by Python. The hosting agent can review evidence and update the local schema, subject to its own permissions/data policies.

Read [schema details](../../../docs/SCHEMA.md) before changing profiles/topics. Preview snapshots the complete source tree; changes after preview can invalidate it, including a growing download. Finish active downloads first. Existing managed folders are not resorted.

Apply journals intent and completion, preserving identity across atomic renames. A crash after intent is recoverable by rerunning the same apply; confirm the plan and journal first. Never blindly delete `operation.lock`, rewrite history, or issue broad recursive shell moves. Verification checks every original item's identity and, for files, size and modification time; cryptographic content verification is added by the backup workflow.

Undo is for unchanged local originals, in reverse run order. It cannot restore a deleted original from the move journal. An imported portable library gets a new owner identifier; its old undo history is read-only, while new refresh runs remain undoable.
