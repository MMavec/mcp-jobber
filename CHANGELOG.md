# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.0] — 2026-05-11

Initial public release.

### Added
- FastMCP server exposing nine `jobber_*` tools over the Jobber GraphQL API:
  `jobber_list_clients`, `jobber_get_client`, `jobber_update_client_tags`,
  `jobber_list_quotes`, `jobber_get_quote`, `jobber_create_note_on_quote`,
  `jobber_list_invoices`, `jobber_list_jobs`, `jobber_search`.
- OAuth 2 authorization-code auth with transparent refresh and disk-cached tokens,
  plus a bearer-token fallback (`JOBBER_PAT`) for quick local use.
- `mcp-jobber-auth` — one-shot OAuth bootstrap helper (local redirect catcher).
- `mcp-jobber-introspect` — dumps the Jobber schema bits the tools depend on so
  field/enum names can be verified per API version.
- Client-side token-bucket rate limiter sized to Jobber's 2500 requests / 5 minutes,
  plus surfacing of `extensions.cost` / `THROTTLED` errors.
- Pytest suite (23 tests) with a fully mocked Jobber API (`httpx.MockTransport`) and
  FastMCP's in-memory client transport. GitHub Actions CI across Python 3.10–3.12.
- README (pipx install, Claude Code / Claude Desktop / Smithery config, example prompts),
  Dockerfile, `smithery.yaml`, demo video script.

### Known limitations
- Some schema-specific details (client-tag filter and tag-edit field, the note-on-quote
  mutation shape, the `quoteStatus` / `invoiceStatus` / `jobStatus` enum spellings,
  whether money is `amounts { total }` or flat `total`) follow Jobber's documented
  conventions but are not yet verified against the live schema — run
  `mcp-jobber-introspect` to confirm.
- `jobber_list_clients` emulates `offset` by over-fetching and slicing rather than
  walking cursors.

[Unreleased]: https://github.com/MMavec/mcp-jobber/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MMavec/mcp-jobber/releases/tag/v0.1.0
