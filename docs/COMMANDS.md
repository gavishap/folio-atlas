# Commands

Run `python scripts/folio.py` from the clone, or use its absolute path. Replace uppercase placeholders with your paths; quote paths containing spaces.

```text
learn --target TARGET --project PROJECT_ONE --project PROJECT_TWO
learn --target TARGET --container PROJECT_CONTAINER
preview --target TARGET
preview --target TARGET --types-only
apply --target TARGET --plan PLAN_FILENAME
verify --target TARGET --plan PLAN_FILENAME
refresh --target TARGET
index --target TARGET
undo --target TARGET --plan PLAN_FILENAME
```

`learn` writes private project profiles; `preview` emits JSON with a private plan and CSV. Inspect both before `apply`. Use the plan's filename from the output. `refresh` creates a preview using existing state; the skill then applies and verifies it when authorized. CLI refresh alone does not move files. `index` rebuilds a snapshot without rearranging files. Undo later runs before earlier ones.

Optional `--keep EXACT_TOP_LEVEL_NAME` repeats on preview/refresh. Permanent protections go in `.folio-atlas/schema.json`. Optional `--read-documents` on learn/preview requires bounded document-reading scope. `--types-only` skips project matching; no-project libraries can refresh without relearning.

Private plans are specific to a target and owner. Do not edit destination fields, import someone else's state, or apply the latest pointer without inspecting its concrete plan. Leave active downloads alone; changes after preview can make the plan stale.

## Backup subcommands

```text
backup build --target TARGET --out OUTSIDE_WORK_FOLDER
backup verify-roundtrip --build BUILD_RECEIPT --downloaded ACTUAL_CLOUD_ZIP --restore-to NEW_RESTORE_FOLDER --cloud-url OBSERVED_DRIVE_URL
backup restore --archive ZIP --destination NEW_FOLDER
backup cleanup-preview --receipt ROUNDTRIP_RECEIPT --scope copies --keep EXACT_NAME
backup cleanup --plan CLEANUP_PLAN --confirm CONFIRMATION_ID --cloud-available
```

`copies` is the default cleanup scope. It removes verified temporary backup/download/restore copies, preserving source files. `originals` or `all` additionally require explicit user authorization and the separate `--delete-originals` execution flag. `--cloud-available` records the agent's recent real cloud-presence check; Python does not check Google Drive itself. See [the full protocol](GOOGLE-DRIVE.md) before using cleanup.

Commands emit results or stop with code 2 and a reason. A verification result may report preserved or failed moves; inspect it, not only the exit code. Cleanup journals and signed receipts remain outside cleanup targets.
