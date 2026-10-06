# Getting started

## Clone and use a local agent

Install Python 3.10+ if needed, then clone the complete repository. The core needs no pip installation:

```sh
git clone https://github.com/gavishap/folio-atlas.git
cd folio-atlas
python scripts/folio.py --version
```

Open the clone as your local agent's workspace. Ask it to read `AGENTS.md`, use Folio Sort, and supply your existing Downloads path and selected project paths. It will learn, inspect a concrete preview, move within Downloads if requested, verify, and create START HERE. For a preview only, explicitly say “preview only.”

Use actual project folders, or a container whose immediate subfolders really are projects. Do not point the target at a drive root, your home, or the source-code repository. If Python is named `python3` on your machine, substitute it in the commands.

Say “Use Folio Refresh to sort my new downloads” on later visits. The private schema stays in Downloads; installing a new copy of the tool does not reset it. Keep that state for recovery and refresh.

## Codex plugin installation

The repository contains a portable root `plugin.json`, a supported `.codex-plugin/plugin.json` compatibility manifest, and a local marketplace catalog. In a Codex version supporting repository marketplaces:

```sh
codex plugin marketplace add gavishap/folio-atlas
```

Open the plugin browser, choose Folio Atlas from the added marketplace, install it, and reload the agent's skills if required. Invoke `$folio-sort`, `$folio-refresh`, or explicitly `$folio-archive`. Surface support can vary; the clone-and-AGENTS workflow remains available. See the official [plugin packaging guide](https://developers.openai.com/plugins/build/plugins) and [skill guide](https://learn.chatgpt.com/docs/build-skills).

Individual skill folders depend on the common engine. Install the **whole package**, not just a copied SKILL.md. The plugin declares no account dependencies, lifecycle hooks, or mandatory connector.

## Other local agents and direct Python

Agents that read repository instructions can use `AGENTS.md`; Claude Code has a `CLAUDE.md` entry point. Other skill loaders can read the canonical `skills/` folders, as long as the complete repository remains beside them. There is no claim of automatic installation on every agent platform.

Optional `python -m pip install .` installs the `folio-atlas` CLI only; it does not register the agent skills globally. PDF text sampling can use `python -m pip install '.[pdf]'` after opting into document reading. Neither is required for normal filename/fingerprint sorting.

See [commands](COMMANDS.md), [schema](SCHEMA.md), and [safety](SAFETY.md).
