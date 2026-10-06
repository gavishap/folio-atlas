# A schema learned from your files

Each target owns `.folio-atlas/owner.json`, `profiles.json` when projects were learned, `schema.json`, and journals. The public repository ships none of these runtime files.

`learn` records project labels, aliases based on actual selected project names, distinctive terms seen in sampled filenames, and bounded eligible document hashes. The agent should review profiles, remove broad aliases, and add distinctive aliases/content phrases only from the user's own evidence. Different projects sharing a term do not make that term distinctive. Exact document fingerprints are content matches, not claims of ownership or legal provenance.

`schema.json` holds optional subject rules and permanently protected top-level names. A fictional example:

```json
{
  "version": 1,
  "keep_names": ["KEEP LOCAL.zip"],
  "topics": [
    {
      "folder": "Workshop Plans",
      "extensions": [".pdf", ".docx"],
      "terms": ["workshop", "curriculum", "facilitator"],
      "minimum_matches": 2
    }
  ]
}
```

A topic rule groups matching filenames below their type folder without changing project attribution. Folder labels must be ordinary single names. Use distinctive terms derived from the actual Downloads inventory. Equal-strength topic matches fall back to default type/subject folders.

Project matches use a threshold and margin, with reasons in every preview. This is a transparent heuristic assisted by the agent's review; it cannot infer every unnamed attachment. Uncertain items remain under By Type. Correct the evidence and regenerate a preview before moving; existing organized files are not automatically reclassified on Refresh.

Keep names are exact direct-child filenames/folder names, not paths or globs. The library, index, and private state are always owned/excluded by the organizer. Refresh reuses the saved schema and only plans incoming loose items.

Changing work: ask your agent to learn an additional explicitly selected project, review the resulting profiles, and preview new arrivals. Relearning project profiles is a deliberate operation. Topic/protection rules and recovery journals remain separate.
