---
name: folio-refresh
description: Re-sort newly downloaded loose files or folders into an existing Folio Atlas library using its saved project profiles and subject schema. Use when a user says refresh, resort, or clean up new downloads after Folio's initial organization. Leave the existing managed library in place, preview incoming assignments, verify moves, and update START HERE. Requires the complete package and Python 3.10+.
---

# Folio Refresh

Use `python scripts/folio.py` from the complete package root or this skill's `scripts/run.py` with an absolute path.

1. Resolve the user's existing target. Read `.folio-atlas/owner.json`, `profiles.json` if present, and `schema.json`. Confirm ownership/root match and inspect prior plans/journals for interrupted operations. Resolve those before starting a refresh. Do not relearn projects or replace the schema automatically.
2. Inspect only new top-level items outside the owned library/index/state. Reuse saved project aliases, distinctive terms, fingerprints, topic rules, and protected names. Existing managed folders and their contents stay in place. New directories are intact bundles. Partial downloads, linked bundles, and exact protected names stay.
3. Run `refresh --target TARGET` to make a preview. Inspect the exact plan/CSV and reasons. Uncertain project assignments use type/subject folders. Ask for new project references only when a meaningful schema update is needed; do not fabricate relationships.
4. An explicit refresh/resort request authorizes these internal moves. Apply the reviewed exact plan with `apply --target TARGET --plan PLAN_FILENAME`, then `verify` with the same plan. Preview-only requests stop before apply. A stale preview needs regeneration; partial runs need recovery from their own journal. Never overwrite or delete files.
5. The apply step rebuilds START HERE. If no moves are needed, run `index --target TARGET`. Report incoming files organized, any preserved/skipped/locked items, and the browser location. Date/size views flatten the library virtually; folder structure remains intact.

For approved schema updates, read [the schema guide](../../docs/SCHEMA.md), derive changes from this user's own evidence, preview again, and preserve existing recovery history. Organization never implies backup, uploads, original-file deletion, a scheduled task, or a watcher. Imported backup histories are read-only; use `backup restore` to relocate and rebind the library before a new refresh.
