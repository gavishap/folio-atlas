# Validation

Tests use only freshly generated fictional files. No prior user's project folders, names, archives, or schemas are included.

The Python suite exercises filename/fingerprint/document evidence, ambiguous fallback, intact folders and saved web resources, collision refusal, stale/tampered plans, unsafe links, crash recovery, undo guards, Refresh stability, and portable index data. Backup cases cover full manifest restore, corrupt downloads, original-ZIP rejection, existing restore refusal, signed-plan tampering, separate deletion scope, protected/new/changed files, and metadata rebinding for a new computer.

Node VM checks the standalone browser's pure date/size/project/search/range/folder-view logic without requiring local HTML browser access. Package checks validate skill metadata, local documentation references, manifests, and public-file packaging. The release builder scans an explicit allowlist for personal paths and credential patterns and records SHA256 for shipped files.

```sh
python -m unittest discover -s tests -v
node tests/test_index.cjs
python tools/check_package.py
python tools/build_release.py --out ../folio-atlas-release-check
```

CI runs the suite on Windows, macOS, and Linux with Python 3.10 and 3.12. Native no-overwrite moves use Windows rename, Linux renameat2, or macOS renamex_np; unsupported systems stop instead of silently weakening the guard. Symlink tests may skip where link creation is unavailable.

Cloud transport is agent/tool-dependent and is not simulated as a real upload by this suite. The tests validate the byte/hash/restore/deletion gates with synthetic downloaded copies, not a live connector. Check a user's actual connector size limits, authentication, upload, genuine download, and remote object presence during the explicitly requested Archive workflow. Classification remains heuristic and deserves preview review.
