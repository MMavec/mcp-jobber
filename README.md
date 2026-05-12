# mcp-jobber

A [Model Context Protocol](https://modelcontextprotocol.io) server that wraps the
[Jobber](https://www.getjobber.com) GraphQL API (`https://api.getjobber.com/api/graphql`),
built with [FastMCP](https://github.com/jlowin/fastmcp). It lets Claude (or any MCP
client) read clients, quotes, invoices, and jobs from a Jobber account, run a global
search, and make a couple of safe writes (client tags, quote notes).

- OAuth 2 authorization-code flow with transparent refresh, plus a bearer-token
  fallback for single-tenant / quick-test setups.
- Client-side throttling sized for Jobber's published limit of **2500 requests / 5 minutes**.
- Nine focused tools, all prefixed `jobber_`.
- Pytest suite with a fully mocked Jobber API (no network, no credentials needed to test).

> **Status: beta.** OAuth, the GraphQL endpoint, the required
> `X-JOBBER-GRAPHQL-VERSION` header, and the rate-limit behaviour are verified
> against Jobber's docs. Some *schema-specific* details in
> [`src/mcp_jobber/queries.py`](src/mcp_jobber/queries.py) — the client-tag filter
> and tag-edit field, the note-on-quote mutation shape, and the `quoteStatus` /
> `invoiceStatus` / `jobStatus` enum spellings — follow Jobber's documented
> conventions but have not been confirmed against the live schema. Run
> `mcp-jobber-introspect` (see [below](#verifying-the-schema)) to confirm them for
> your API version and tweak `queries.py` if needed before leaning on the write tools.

---

## Tools

| Tool | Arguments | What it does |
|------|-----------|--------------|
| `jobber_list_clients` | `limit`, `offset`, `tags` | List clients, optionally filtered to those carrying all of `tags`. |
| `jobber_get_client` | `client_id` | Fetch one client (emails, phones, tags, timestamps). |
| `jobber_update_client_tags` | `client_id`, `tags` | **Write.** Replace a client's tag list. |
| `jobber_list_quotes` | `status`, `client_id`, `updated_after` | List quotes, filtered by status / client / `updatedAfter`. |
| `jobber_get_quote` | `quote_id` | Fetch a quote with line items and notes. |
| `jobber_create_note_on_quote` | `quote_id`, `body` | **Write.** Attach a note to a quote. |
| `jobber_list_invoices` | `client_id`, `paid_status`, `date_from`, `date_to` | List invoices by client / paid status / issued-date range. |
| `jobber_list_jobs` | `status`, `completed_after` | List jobs by status / completion date. |
| `jobber_search` | `text` | Global search across clients, jobs, quotes, invoices (results partitioned by type). |

Write tools return `{"ok": false, "errors": [...]}` when Jobber reports `userErrors`
instead of raising, so the model can react.

---

## Installation

### pipx (recommended)

```bash
pipx install mcp-jobber
```

This puts three commands on your PATH:

- `mcp-jobber` — the MCP server (speaks stdio; you normally don't run it by hand).
- `mcp-jobber-auth` — one-shot helper that completes the OAuth flow and prints your
  `JOBBER_REFRESH_TOKEN`.
- `mcp-jobber-introspect` — dumps the Jobber schema bits the tools depend on, so you
  can confirm field/enum names for your API version.

From a checkout instead:

```bash
git clone https://github.com/MMavec/mcp-jobber
cd mcp-jobber
pipx install .
# or, for development:  pip install -e ".[dev]"
```

---

## Authentication

You can run in **OAuth mode** (recommended) or **PAT mode** (fallback).

### OAuth 2 (recommended)

1. Create an app in the [Jobber Developer Center](https://developer.getjobber.com/).
   Set its redirect URI to `http://localhost:8976/callback` (or anything you like;
   match it in `JOBBER_REDIRECT_URI`).
2. Export the app credentials:

   ```bash
   export JOBBER_CLIENT_ID=...
   export JOBBER_CLIENT_SECRET=...
   export JOBBER_REDIRECT_URI=http://localhost:8976/callback
   ```

3. Run the bootstrap helper:

   ```bash
   mcp-jobber-auth
   ```

   It opens Jobber's consent screen, catches the redirect, exchanges the code, writes
   the token bundle to `~/.cache/mcp-jobber/tokens.json`, and prints:

   ```
   JOBBER_REFRESH_TOKEN=...
   ```

4. Keep `JOBBER_CLIENT_ID`, `JOBBER_CLIENT_SECRET`, and `JOBBER_REFRESH_TOKEN` in your
   environment (or the MCP client config below). The server swaps the refresh token for
   an access token on startup and refreshes it automatically ~60 s before expiry; the
   refreshed bundle is re-cached to disk so restarts don't burn a refresh.

### Bearer-token fallback (`JOBBER_PAT`)

Jobber does not currently issue "personal access tokens" — the only documented
credential is an OAuth access token. But if you already have a valid bearer token in
hand (for example, a still-valid OAuth access token you grabbed for a quick test),
you can skip the refresh machinery entirely:

```bash
export JOBBER_PAT=...
```

When `JOBBER_PAT` is set and no OAuth refresh token is configured, the server sends it
verbatim as `Authorization: Bearer <token>` and never tries to refresh — so it will
stop working when that token expires (Jobber access tokens last ~60 minutes). For
anything beyond a quick test, use OAuth mode.

### All settings

| Env var | Default | Notes |
|---------|---------|-------|
| `JOBBER_CLIENT_ID` / `JOBBER_CLIENT_SECRET` | — | OAuth app credentials |
| `JOBBER_REFRESH_TOKEN` | — | from `mcp-jobber-auth` |
| `JOBBER_REDIRECT_URI` | `http://localhost:8976/callback` | must match the app's registered URI |
| `JOBBER_PAT` | — | PAT-mode token (used only if no refresh token) |
| `JOBBER_API_URL` | `https://api.getjobber.com/api/graphql` | |
| `JOBBER_OAUTH_AUTHORIZE_URL` | `https://api.getjobber.com/api/oauth/authorize` | |
| `JOBBER_OAUTH_TOKEN_URL` | `https://api.getjobber.com/api/oauth/token` | |
| `JOBBER_GRAPHQL_VERSION` | `2025-04-16` | sent as `X-JOBBER-GRAPHQL-VERSION`; must be an active version date from Jobber's [changelog](https://developer.getjobber.com/docs/changelog/) |
| `JOBBER_TOKEN_CACHE` | `~/.cache/mcp-jobber/tokens.json` | chmod 600 |
| `JOBBER_RATE_CAPACITY` | `2500` | token-bucket capacity |
| `JOBBER_RATE_WINDOW_SECONDS` | `300` | refill window |

A `.env` file in the working directory is read automatically (see
[`.env.example`](.env.example)).

---

## Configure your MCP client

### Claude Code

Add the server with the CLI:

```bash
claude mcp add jobber -- mcp-jobber
```

Then add the credentials to the generated entry (or set them in your shell). The
project-scoped `.mcp.json` ends up looking like:

```json
{
  "mcpServers": {
    "jobber": {
      "command": "mcp-jobber",
      "env": {
        "JOBBER_CLIENT_ID": "your_client_id",
        "JOBBER_CLIENT_SECRET": "your_client_secret",
        "JOBBER_REFRESH_TOKEN": "your_refresh_token"
      }
    }
  }
}
```

(For PAT mode, replace the three OAuth vars with `"JOBBER_PAT": "..."`.)

### Claude Desktop

Edit `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "jobber": {
      "command": "mcp-jobber",
      "env": {
        "JOBBER_CLIENT_ID": "your_client_id",
        "JOBBER_CLIENT_SECRET": "your_client_secret",
        "JOBBER_REFRESH_TOKEN": "your_refresh_token"
      }
    }
  }
}
```

If `mcp-jobber` is not on the PATH that the desktop app sees, use the absolute path
(`pipx environment --value PIPX_BIN_DIR` will tell you where pipx put it), or invoke via
`pipx run mcp-jobber`.

Restart Claude Desktop after editing the file.

### Claude Desktop via an `.mcpb` bundle (one-click)

Instead of editing JSON, you can build a bundle and double-click it:

```bash
bash scripts/build-mcpb.sh    # produces ./mcp-jobber.mcpb
```

Open `mcp-jobber.mcpb` (Claude Desktop → Settings → Extensions → Install) and it will
prompt for the `JOBBER_*` values declared in [`manifest.json`](manifest.json). The build
script bundles the package and its dependencies (MCPB requires deps to be vendored, not
pip-installed at runtime); it uses the `@anthropic-ai/mcpb` CLI via `npx` if available,
otherwise plain `zip`. Because some dependencies pull in a compiled extension
(cffi/cryptography), the resulting bundle is specific to the OS and Python version that
built it — build it on the machine you'll run it on, or build one bundle per platform.

### Smithery

[Smithery](https://smithery.ai) currently lists servers two ways, both at
`smithery.ai/new`:

- **Upload the `.mcpb` bundle** built above — this matches what this server is (a stdio
  server). Recommended.
- **Bring-your-own-hosting (URL)** — paste the HTTPS URL of an instance you host with the
  HTTP transport (see [Running over HTTP](#running-over-http-hosted) below); Smithery's
  gateway proxies to it.

(The [`smithery.yaml`](smithery.yaml) in this repo targets Smithery's older
GitHub/Dockerfile deploy flow; it is kept for reference but the two paths above are the
current ones.)

---

## Example prompts

Once the server is connected, try:

- "List my Jobber clients tagged `roof-maxx`."
- "Show me quote Q-1042 with its line items."
- "Add a note to that quote: customer asked to push the start date to June."
- "Which invoices for Acme Property Mgmt are still awaiting payment?"
- "Tag client `Z2lkOi8v...` with `vip` and `2026-spring-campaign`." (replaces existing tags)
- "What jobs were completed since April 1st?"
- "Search Jobber for 'gutter cleaning' and tell me which clients and jobs match."
- "List quotes that changed since yesterday so I can review what my team sent out."

---

## Rate limiting

Jobber publishes a limit of **2500 requests per rolling 5 minutes**. The server runs
every GraphQL call through an async token bucket (`capacity=2500`, refilling at
`2500 / 300 s ≈ 8.3 req/s`), so a burst is allowed up to the cap and then calls are
paced automatically — you won't normally see request-count 429s.

Jobber *also* applies a query-cost ("points") throttle independent of request count.
That one can still return a throttle error; when it does, the GraphQL client raises a
`JobberGraphQLError` and the tool surfaces the message to the model. The most recent
cost block from `extensions.cost` is kept on `JobberClient.last_cost` for diagnostics.

---

## Running over HTTP (hosted)

By default the server speaks stdio (what Claude Desktop / Claude Code expect). To run it
as a network service using MCP's Streamable HTTP transport:

```bash
mcp-jobber --http --host 0.0.0.0 --port 8000
# or, equivalently, via env:
MCP_TRANSPORT=http JOBBER_HTTP_HOST=0.0.0.0 JOBBER_HTTP_PORT=8000 mcp-jobber
```

The bundled [`Procfile`](Procfile) (`web: mcp-jobber --http --host 0.0.0.0 --port ${PORT:-8000}`)
works on most PaaS hosts (Render, Railway, Fly.io, etc.). The MCP endpoint is then at
`https://<your-host>/mcp` — that's the URL you'd paste into Smithery's "bring your own
hosting" form.

> ⚠️ This serves the **single-tenant** server: it uses the `JOBBER_*` credentials in its
> own environment for every request. It is not a multi-tenant gateway and has no built-in
> request auth. Do not expose it on the public internet without putting your own
> authentication / network controls in front of it.

## Verifying the schema

Jobber's GraphQL schema is only browsable from inside the Developer Center's GraphiQL,
so a few field and enum names in [`src/mcp_jobber/queries.py`](src/mcp_jobber/queries.py)
are written to Jobber's documented conventions rather than confirmed byte-for-byte.
Once you have credentials configured, run:

```bash
mcp-jobber-introspect            # add --json to also dump the raw introspection result
```

It prints the fields/args of `Client`, `Quote`, `Invoice`, `Job`, their filter input
types, the `*StatusTypeEnum` enums, and any `note*` mutations. Compare that with
`queries.py` and adjust:

- the `tags` filter on `ClientFilterAttributes` and the shape of `Client.tags`
- whether `ClientEditInput` takes a `tags` field (the `jobber_update_client_tags` write)
- the `noteCreate` mutation name / input fields (the `jobber_create_note_on_quote` write)
- the `quoteStatus` / `invoiceStatus` / `jobStatus` enum values you pass to the list tools
- whether money is `amounts { total }` or a flat `total`

Read tools degrade gracefully (a wrong nested field just comes back null); the two
write tools are the ones worth confirming before production use.

## Development

```bash
pip install -e ".[dev]"
pytest            # all tests, fully mocked — no Jobber account needed
ruff check .
```

The test suite (`tests/`) uses `httpx.MockTransport` to stand in for
`api.getjobber.com`, including the OAuth token endpoint, and drives the tools through
FastMCP's in-memory client transport. See [`tests/conftest.py`](tests/conftest.py) for
the `FakeJobber` helper.

---

## Roadmap

- A thin npm wrapper (`npx mcp-jobber`) once the Python package stabilizes — the Python
  build is canonical for now.
- Pagination cursors exposed on list tools (today `jobber_list_clients` emulates
  `offset` by over-fetching and slicing).
- More write tools (create quote, convert quote to job) gated behind an opt-in env flag.

## License

[MIT](LICENSE) © Vic Home Pros.

This project is not affiliated with or endorsed by Jobber / Octopusapp Inc.
