# mcp-jobber — Demo Video Script

A tight ~3 minute screen recording. Goal: show a real person asking Claude to do
Jobber work in plain English, and Claude doing it through `mcp-jobber`. Keep it
concrete — use one customer thread the whole way through so it feels like a real day.

Recommended setup before you hit record:
- Claude Desktop (or Claude Code) with the `jobber` server already configured and
  connected (green dot / tool list visible).
- A Jobber sandbox or a real account where you don't mind a note being added.
- Pick one client up front, e.g. "Acme Property Management", that has at least one
  quote and one invoice.
- Terminal window open for the 15-second install beat.

---

## Beat 0 — Cold open (0:00–0:12)

**On screen:** Claude chat, empty.

**Voiceover:**
> "This is Jobber — clients, quotes, invoices, jobs. And this is Claude. With the
> mcp-jobber server, Claude can just... use Jobber. No tab switching. Watch."

---

## Beat 1 — Install (0:12–0:30)

**On screen:** terminal.

**Type / show:**
```bash
pipx install mcp-jobber
mcp-jobber-auth          # browser pops, you click "Allow", it prints a refresh token
claude mcp add jobber -- mcp-jobber
```

**Voiceover:**
> "One install. One OAuth click — the helper catches the redirect and hands you a
> refresh token. Drop it in your MCP config and you're done. It works the same in
> Claude Desktop and Claude Code."

(Cut to Claude Desktop with the `jobber` server showing 9 tools.)

---

## Beat 2 — Read: who is this client (0:30–1:00)

**Prompt (type it live):**
> "Pull up Acme Property Management in Jobber — show me their contact info and any tags."

**Expected:** Claude calls `jobber_search` then `jobber_get_client`, returns name,
emails, phones, tags.

**Voiceover:**
> "It searched, found the client, and pulled the full record. Notice the tags — we'll
> come back to those."

---

## Beat 3 — Read: open quotes & money owed (1:00–1:35)

**Prompt:**
> "What quotes have we sent Acme, and which invoices are still unpaid?"

**Expected:** `jobber_list_quotes` with `client_id`, then `jobber_list_invoices` with
`paid_status` = AWAITING_PAYMENT. Claude summarizes: "Quote Q-1042 ($4,800, awaiting
response) and invoice INV-318 ($1,200, awaiting payment)."

**Voiceover:**
> "Two calls, one answer. This is the part that normally means three screens and a
> spreadsheet."

---

## Beat 4 — Write: leave a note on the quote (1:35–2:05)

**Prompt:**
> "Add a note to quote Q-1042: customer called, wants to push the start date to June 3rd,
> follow up Friday."

**Expected:** Claude calls `jobber_create_note_on_quote`. It returns `ok: true` with the
note id. Cut to the Jobber web UI showing the new note on the quote.

**Voiceover:**
> "And it writes back. The note is on the quote in Jobber, timestamped, right now. The
> write tools are deliberately narrow — tags and notes — so Claude can't wander off and
> change pricing."

---

## Beat 5 — Write: re-tag the client (2:05–2:35)

**Prompt:**
> "Tag Acme with 'vip' and '2026-spring-followup'. Keep their existing tags too."

**Expected:** Claude reads current tags via `jobber_get_client`, then calls
`jobber_update_client_tags` with the merged list (because the tool replaces, and the
docstring tells the model that). Cut to Jobber UI showing the tags.

**Voiceover:**
> "It knew to read the current tags first and merge — because the tool tells the model
> it replaces the whole list. Little guardrails like that are baked in."

---

## Beat 6 — The "so what" (2:35–3:00)

**On screen:** back to chat, scroll up through the conversation.

**Voiceover:**
> "Nine tools — clients, quotes, invoices, jobs, search. OAuth with automatic refresh,
> or just hand it a bearer token for a quick test. Client-side rate limiting so you
> never trip Jobber's 2500-requests-per-five-minutes cap. MIT licensed, on GitHub, on
> PyPI, on Smithery. That's mcp-jobber."

**End card:** `github.com/MMavec/mcp-jobber` · `pipx install mcp-jobber`

---

## Shot list / B-roll cheatsheet

| Time | Capture |
|------|---------|
| 0:12 | Terminal: the three install commands, real output |
| 0:25 | Browser: the Jobber consent screen, click "Allow" |
| 0:28 | Claude Desktop settings → the `jobber` server, 9 tools listed |
| 0:45 | Claude's tool-call chips expanding (`jobber_search`, `jobber_get_client`) |
| 1:50 | Jobber web UI: the new note appearing on Q-1042 |
| 2:20 | Jobber web UI: the client's tag chips updating |
| 2:50 | GitHub repo page + PyPI page (quick crossfade) |

## Things to NOT do on camera
- Don't show real client PII — use a sandbox or blur emails/phones in post.
- Don't show the refresh token or client secret on screen (the `mcp-jobber-auth`
  output and the MCP config). Blur them.
- Don't run a `jobber_update_client_tags` against a client whose tags you care about —
  remember it replaces the list.

## Optional 30-second cut (for social)
Beats 0 → 2 → 4 only: "Here's Jobber. Here's Claude. 'Add a note to quote Q-1042...'
Done. mcp-jobber, link in bio."
