# Safety model and limits

## Organization

All original moves stay inside the named existing target. Drive roots and home directories are rejected. Project references are read-only and outside the target. The engine refuses existing destination collisions, linked/junction paths, changed previews, and unowned reserved state/index paths. Collisions receive new names in the preview rather than overwriting files.

Existing folders are intact bundles. Saved HTML/resource pairs and recognizable loose source-code groups remain together. Bundles containing links/special entries stay at source. Incomplete downloads are excluded from moves. A growing download can invalidate the whole preview because preservation is checked across the source tree; finish downloads first.

An intent journal is flushed before each atomic no-overwrite rename. Restart a partial operation with its exact plan after inspecting its journal and lock. A stale untouched plan must be regenerated. Move verification checks identity, size, and modification time; it is not a full content hash scan. Undo refuses changed files and occupied original destinations. It leaves empty scaffolding instead of deleting directories.

## Optional backup and cleanup

Backups use ZIP64 and SHA256 for every regular file, preserve empty directories, and record original date metadata. Windows-incompatible archive names are rejected for portable restoration. Symlinks/junctions are recorded without traversing or recreating their external targets. This is not a disk image, application installer, or preservation of every filesystem permission/stream.

Cleanup requires a signed local proof of a matching full cloud download and complete restore, less than 24 hours old, plus actual cloud-presence confirmation by the agent. Local receipts are HMAC-signed with a private work-directory key to prevent accidental editing; this is not protection against someone who controls that key or a compromised local agent. Cloud provenance is observed by the agent, not independently certified by Python.

Current regular-file SHA256/size are compared with the verified manifest before original deletion and checked again against the reviewed cleanup plan. Deletion is individual verified file unlinking and empty-directory removal. New, changed, unbacked, protected, linked, or locked content is preserved. The source root, private organizer state, index, and cloud object are never removed. All receipt/journal evidence lives outside cleanup scope.

Do not run while other programs change the same files or trees. Checks reduce accidental data loss, but are not an isolation boundary against a malicious concurrent process. No tool can guarantee a cloud account will remain accessible forever; keep an independent backup for irreplaceable material according to your needs.

There is no background watcher, auto-cleanup, deduplication deletion, uploaded code execution, permission takeover, or cloud-delete command. A backup request alone never authorizes local deletion. See [the transfer protocol](GOOGLE-DRIVE.md).
