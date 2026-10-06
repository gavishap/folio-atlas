# Maintainer publishing guide

GitHub distribution lets anyone clone the full engine and skills. It does **not** automatically list the plugin in ChatGPT/Codex's public directory.

1. Change the semantic version consistently in `plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `folio_atlas/__init__.py`, and `organizer.py`.
2. Run `python -m unittest discover -s tests -v`, `node tests/test_index.cjs`, and `python tools/check_package.py`. Review synthetic tests and private-data exclusions.
3. Build into a new outside-repository folder: `python tools/build_release.py --out NEW_RELEASE_FOLDER`. It uses an explicit file allowlist and privacy scan; no inventories/profiles/archives from a user enter the package.
4. Commit only allowlisted public files; push to the public GitHub repo and wait for platform CI. Tag the release and attach the public ZIP plus its SHA256 inventory. Do not upload a user's portable backup or receipt key.
5. Share `https://github.com/gavishap/folio-atlas`, the release link, and the README's clone/prompt instructions. Record videos with the synthetic demo.
6. For public plugin-directory submission, follow the current official [packaging/submission guidance](https://developers.openai.com/plugins/build/plugins), review listing/privacy fields, test supported local execution, and submit through the platform's current process. Marketplace review/discovery remains separate; do not claim official approval from a GitHub release alone.

The included local marketplace and compatibility manifest support development/team installation. Agent Plugins root `plugin.json` and root `skills/` are the canonical package. No cloud credentials, optional account dependencies, MCP server, or execution hook is registered.
