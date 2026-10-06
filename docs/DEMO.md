# A video-ready fictional workspace

Use a new named directory outside the repository. The generator refuses an existing directory; it never reads your actual Downloads or projects.

```sh
python tools/create_demo.py --out ../folio-atlas-demo
```

It creates an Inbox and two fictional reference projects: Juniper Studio and Harbor Ledger. Files include project contracts, spreadsheets, a resume, a WhatsApp recording, a saved web-page bundle, and a preserved folder. Dates and sizes are deliberately varied for the browser demo.

Open the repository in your local agent and prompt:

> Read AGENTS.md and use Folio Sort on the synthetic Inbox in my demo folder. Learn from its Projects container, inspect the preview, organize without deleting, keep KEEP LOCAL.zip at the root, and show START HERE.

Or prepare the already organized version in one command:

```sh
python tools/create_demo.py --out ../folio-atlas-demo-ready --organize
```

## A 60-second story

1. **0–10s:** Show the scattered fictional Inbox. “Downloads should show what you’re working on.”
2. **10–25s:** Show project folders, learned evidence, and the preview. “It learns these projects on this machine.”
3. **25–40s:** Open START HERE. Switch between projects, newest files, and largest files. Open a project document through its relative link.
4. **40–50s:** Add a fresh batch: `python tools/create_demo.py --add-arrivals ../folio-atlas-demo-ready`. Ask Folio Refresh to sort it. Existing library folders stay in place.
5. **50–60s:** Show the optional Archive workflow. Explain real cloud download plus full restore verification before separately requested local cleanup. Do not pretend a synthetic local copy proves a live cloud upload.

The README animation is an original typographic route map, built by `tools/render_banner.py`. To regenerate it, install Pillow in a development environment and run the script. Use the provided GIF/PNG for title cards. The demo uses invented names only; do not substitute private files or publicize your generated real index.
