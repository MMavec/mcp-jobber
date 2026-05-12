"""FastMCP server exposing Jobber operations as MCP tools."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from . import queries
from .auth import JobberAuth
from .client import JobberClient
from .config import Settings, load_settings


def build_server(
    *,
    settings: Settings | None = None,
    client: JobberClient | None = None,
) -> FastMCP:
    """Construct a FastMCP instance. Accepts injected client for tests."""

    settings = settings or load_settings()
    if client is None:
        auth = JobberAuth(settings)
        client = JobberClient(settings, auth)

    mcp = FastMCP(
        name="mcp-jobber",
        instructions=(
            "Tools wrap Jobber's GraphQL API for a home-services CRM. "
            "Clients, quotes, invoices, jobs, and a global search. "
            "Mutations (tags, notes) are write operations; confirm intent before calling."
        ),
    )

    # ---------- Clients ----------

    @mcp.tool()
    async def jobber_list_clients(
        limit: Annotated[int, Field(ge=1, le=100, description="Max clients to return")] = 25,
        offset: Annotated[int, Field(ge=0, description="How many leading clients to skip")] = 0,
        tags: Annotated[list[str] | None, Field(description="Only include clients with ALL of these tag labels")] = None,
    ) -> dict[str, Any]:
        """List clients, optionally filtered by tag labels.

        Jobber uses cursor pagination; this tool simulates an offset by
        fetching `limit+offset` rows and discarding the first `offset`. Use
        modest offsets (<= a few hundred) to keep per-call cost bounded.
        """
        filter_: dict[str, Any] = {}
        if tags:
            filter_["tags"] = tags

        variables = {"first": limit + offset, "filter": filter_ or None}
        data = await client.execute(queries.LIST_CLIENTS, variables)
        nodes = data.get("clients", {}).get("nodes", [])
        return {
            "clients": nodes[offset : offset + limit],
            "total_count": data.get("clients", {}).get("totalCount"),
            "has_more": data.get("clients", {}).get("pageInfo", {}).get("hasNextPage", False),
        }

    @mcp.tool()
    async def jobber_get_client(
        client_id: Annotated[str, Field(description="Jobber encoded client ID")],
    ) -> dict[str, Any]:
        """Fetch a single client by its Jobber ID (an EncodedId string)."""
        data = await client.execute(queries.GET_CLIENT, {"id": client_id})
        return {"client": data.get("client")}

    @mcp.tool()
    async def jobber_update_client_tags(
        client_id: Annotated[str, Field(description="Jobber encoded client ID")],
        tags: Annotated[list[str], Field(description="Full replacement set of tag labels")],
    ) -> dict[str, Any]:
        """Replace a client's tag list with the provided labels.

        This is a write operation. The tag list is REPLACED, not merged; read
        the client's current tags first if you only want to add/remove some.
        """
        data = await client.execute(
            queries.UPDATE_CLIENT_TAGS,
            {"id": client_id, "tags": tags},
        )
        result = data.get("clientEdit") or {}
        if result.get("userErrors"):
            return {"ok": False, "errors": result["userErrors"]}
        return {"ok": True, "client": result.get("client")}

    # ---------- Quotes ----------

    @mcp.tool()
    async def jobber_list_quotes(
        status: Annotated[str | None, Field(description="One of DRAFT, AWAITING_RESPONSE, APPROVED, CONVERTED, ARCHIVED")] = None,
        client_id: Annotated[str | None, Field(description="Restrict to quotes for this client ID")] = None,
        updated_after: Annotated[str | None, Field(description="ISO-8601 timestamp; quotes updated strictly after this")] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 25,
    ) -> dict[str, Any]:
        """List quotes, filtered by status, client, and/or updatedAfter."""
        filter_: dict[str, Any] = {}
        if status:
            filter_["status"] = status
        if client_id:
            filter_["clientId"] = client_id
        if updated_after:
            filter_["updatedAfter"] = updated_after

        variables = {"first": limit, "filter": filter_ or None}
        data = await client.execute(queries.LIST_QUOTES, variables)
        return {
            "quotes": data.get("quotes", {}).get("nodes", []),
            "total_count": data.get("quotes", {}).get("totalCount"),
        }

    @mcp.tool()
    async def jobber_get_quote(
        quote_id: Annotated[str, Field(description="Jobber encoded quote ID")],
    ) -> dict[str, Any]:
        """Fetch a quote, including line items and notes."""
        data = await client.execute(queries.GET_QUOTE, {"id": quote_id})
        return {"quote": data.get("quote")}

    @mcp.tool()
    async def jobber_create_note_on_quote(
        quote_id: Annotated[str, Field(description="Jobber encoded quote ID")],
        body: Annotated[str, Field(min_length=1, description="Note text; supports plain text")],
    ) -> dict[str, Any]:
        """Attach a new note to a quote. Write operation; not idempotent."""
        data = await client.execute(
            queries.CREATE_NOTE_ON_QUOTE,
            {"quoteId": quote_id, "body": body},
        )
        result = data.get("noteCreate") or {}
        if result.get("userErrors"):
            return {"ok": False, "errors": result["userErrors"]}
        return {"ok": True, "note": result.get("note")}

    # ---------- Invoices ----------

    @mcp.tool()
    async def jobber_list_invoices(
        client_id: Annotated[str | None, Field(description="Restrict to invoices for this client ID")] = None,
        paid_status: Annotated[str | None, Field(description="One of DRAFT, AWAITING_PAYMENT, PARTIALLY_PAID, PAID, BAD_DEBT")] = None,
        date_from: Annotated[str | None, Field(description="ISO-8601; issued on or after")] = None,
        date_to: Annotated[str | None, Field(description="ISO-8601; issued on or before")] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 25,
    ) -> dict[str, Any]:
        """List invoices filtered by client, paid-status, and issued-date range."""
        filter_: dict[str, Any] = {}
        if client_id:
            filter_["clientId"] = client_id
        if paid_status:
            filter_["invoiceStatus"] = paid_status
        if date_from:
            filter_["issuedAfter"] = date_from
        if date_to:
            filter_["issuedBefore"] = date_to

        variables = {"first": limit, "filter": filter_ or None}
        data = await client.execute(queries.LIST_INVOICES, variables)
        return {
            "invoices": data.get("invoices", {}).get("nodes", []),
            "total_count": data.get("invoices", {}).get("totalCount"),
        }

    # ---------- Jobs ----------

    @mcp.tool()
    async def jobber_list_jobs(
        status: Annotated[str | None, Field(description="One of ACTIVE, COMPLETED, ARCHIVED, ON_HOLD, REQUIRES_INVOICING")] = None,
        completed_after: Annotated[str | None, Field(description="ISO-8601; jobs completed strictly after")] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 25,
    ) -> dict[str, Any]:
        """List jobs filtered by status and/or completion date."""
        filter_: dict[str, Any] = {}
        if status:
            filter_["status"] = status
        if completed_after:
            filter_["completedAfter"] = completed_after

        variables = {"first": limit, "filter": filter_ or None}
        data = await client.execute(queries.LIST_JOBS, variables)
        return {
            "jobs": data.get("jobs", {}).get("nodes", []),
            "total_count": data.get("jobs", {}).get("totalCount"),
        }

    # ---------- Search ----------

    @mcp.tool()
    async def jobber_search(
        text: Annotated[str, Field(min_length=1, description="Free-text search across clients, jobs, quotes, invoices")],
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
    ) -> dict[str, Any]:
        """Global search across clients, jobs, quotes, and invoices.

        Returned object is partitioned by entity type so the caller can pick
        the most relevant match without re-parsing a merged list.
        """
        data = await client.execute(queries.SEARCH, {"text": text, "first": limit})
        return {
            "clients": data.get("clients", {}).get("nodes", []),
            "jobs": data.get("jobs", {}).get("nodes", []),
            "quotes": data.get("quotes", {}).get("nodes", []),
            "invoices": data.get("invoices", {}).get("nodes", []),
        }

    return mcp


def main() -> None:
    import sys

    try:
        server = build_server()
    except RuntimeError as exc:
        # Most commonly: no credentials configured. MCP clients surface stderr.
        print(f"mcp-jobber: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    server.run()
