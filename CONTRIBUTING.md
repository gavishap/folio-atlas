# Contributing

Use only synthetic data. Read AGENTS.md, preserve explicit deletion scope and containment guards, and add behavioral tests for meaningful preservation/recovery changes. Default sorting must stay offline with no required dependencies.

Run the commands in VALIDATION.md. Add any new public file to the explicit allowlist in `tools/build_release.py`; never solve packaging by zipping the whole working directory. Keep shared mechanics in `folio_atlas/` and skill instructions concise. For schema/classification changes, verify an ambiguous file still falls back safely and Refresh leaves the old library unchanged.
