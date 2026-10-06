# Privacy

The distributed package contains code, generic instructions, original branding, and fictional demo generation. It contains no prior user's filenames, paths, project profiles, document text, inventories, archives, or credentials. The demo projects Juniper Studio and Harbor Ledger are invented.

The default Python organizer has no network requests, telemetry, cloud account, or model API. It reads the selected target and selected local reference project folders. It learns filenames and a bounded set of eligible document SHA256 fingerprints. Optional document reading samples bounded local text. Common sensitive filenames are excluded from text/fingerprint sampling; filename heuristics cannot identify every sensitive file. Select reference folders deliberately.

Private state is created in the user's target under `.folio-atlas/`. The HTML index, project profiles, schema, CSV previews, paths, fingerprints, and move journals can disclose personal information. Do not publish or attach them to a public issue. The hosting assistant may see the filenames/evidence it reads and follows its own provider's data policies.

Backup is explicitly requested and packages the user's files and private state. That personal archive is intentionally private. Local ZIPs are not encrypted by Folio; protect the work directory and choose appropriate Drive access. Receipts and their local signing key stay outside deletion scope, contain private paths/inventories, and must never enter this public repository. Linked external files are not copied.

Google Drive transfer is performed by the user's existing connector, approved browser tools, or manual handoff, subject to those services' policies. Folio stores no cloud credentials and has no cloud-deletion operation. Local deletion is a separately authorized workflow gated by actual cloud download and full file verification.

Maintainer: [gavishap](https://github.com/gavishap). Report problems without private artifacts through [issues](https://github.com/gavishap/folio-atlas/issues); see [security reporting](SECURITY.md).
