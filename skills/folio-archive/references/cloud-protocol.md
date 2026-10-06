# The cloud protocol

Use the workflow in [docs/GOOGLE-DRIVE.md](../../../docs/GOOGLE-DRIVE.md), including the exact CLI arguments. Receipts and their local key must remain together in an outside-target working folder. A signed receipt proves that this local engine performed checks; it is not independent proof that the archive came from a cloud service. The agent must observe the upload and genuine download through the connector/browser/manual handoff.

## Gates before any deletion

1. The user explicitly requested the relevant deletion scope.
2. Build completed with all regular files in its SHA256 manifest.
3. An observed, completed download of the actual cloud object matches the entire ZIP's byte count and SHA256. A browser partial or original local archive is rejected.
4. A new restore passes every file hash and exact file/directory inventory, plus generated index links, dates, and sizes where present.
5. The signed verification is less than 24 hours old; its key and receipts remain private and outside cleanup scope.
6. The agent has just confirmed the remote object still exists and is accessible. Only then pass `--cloud-available`; this flag is an attestation by the agent, not a cloud API check by Python.
7. Review the signed cleanup plan and current preserved content. Deleting originals requires separate scope and `--delete-originals`.

If authentication, transfer limits, security restrictions, insufficient space, a stalled download, changed files, or restore errors prevent a gate, keep all originals and report the concrete issue. Do not bypass blocks. Do not resume a partial extraction into the same folder or execute scripts from an uploaded ZIP. Choose a separately named empty restore destination after inspecting prior evidence.

Use the current connector's advertised operations and size limits, not remembered capabilities. Large downloads/restores can need several archive sizes of free space. Inspect available space before starting. During long transfers, wait with bounded checks; notify on completion, failure, or required action rather than on each unchanged poll. Monitoring must be separately requested; keep progress outside deletion scope.

Backup does not dereference symbolic links or junctions. Their target paths are recorded, but linked external data is not copied and live links are not recreated on restore. Never describe linked external content as backed up. Any original link entry and its containing nonempty folder remain during cleanup.
