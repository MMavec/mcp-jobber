"""End-to-end tool tests via FastMCP's in-memory client transport."""

from __future__ import annotations

import json

from fastmcp import Client


def _payload(result) -> dict:
    """Extract the JSON-decoded payload from an MCP tool result.

    FastMCP returns structured `.data` when a tool returns a dict; older
    transports return a list of TextContent blocks with JSON in the first one.
    Handle both so the tests don't pin a single FastMCP version.
    """
    if getattr(result, "data", None) is not None:
        return result.data
    blocks = result.content if hasattr(result, "content") else result
    first = blocks[0]
    text = getattr(first, "text", first)
    return json.loads(text)


async def test_list_clients_applies_offset(mcp_server, fake_jobber):
    nodes = [{"id": f"c_{i}", "firstName": f"First{i}"} for i in range(5)]
    fake_jobber.respond_to(
        "ListClients",
        {
            "clients": {
                "nodes": nodes,
                "totalCount": 5,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        },
    )
    async with Client(mcp_server) as c:
        result = await c.call_tool("jobber_list_clients", {"limit": 2, "offset": 2})
    data = _payload(result)
    assert [cl["id"] for cl in data["clients"]] == ["c_2", "c_3"]
    assert data["total_count"] == 5


async def test_get_client(mcp_server, fake_jobber):
    fake_jobber.respond_to("GetClient", {"client": {"id": "c_42", "firstName": "Marie"}})
    async with Client(mcp_server) as c:
        result = await c.call_tool("jobber_get_client", {"client_id": "c_42"})
    assert _payload(result)["client"]["firstName"] == "Marie"


async def test_update_client_tags_success(mcp_server, fake_jobber):
    fake_jobber.respond_to(
        "UpdateClientTags",
        {"clientEdit": {"client": {"id": "c_1", "tags": {"nodes": [{"label": "VIP"}]}}, "userErrors": []}},
    )
    async with Client(mcp_server) as c:
        result = await c.call_tool(
            "jobber_update_client_tags",
            {"client_id": "c_1", "tags": ["VIP"]},
        )
    data = _payload(result)
    assert data["ok"] is True
    assert fake_jobber.calls[-1]["variables"] == {"id": "c_1", "tags": ["VIP"]}


async def test_update_client_tags_user_errors(mcp_server, fake_jobber):
    fake_jobber.respond_to(
        "UpdateClientTags",
        {"clientEdit": {"client": None, "userErrors": [{"message": "bad tag", "path": ["tags"]}]}},
    )
    async with Client(mcp_server) as c:
        result = await c.call_tool(
            "jobber_update_client_tags",
            {"client_id": "c_1", "tags": [""]},
        )
    data = _payload(result)
    assert data["ok"] is False
    assert data["errors"][0]["message"] == "bad tag"


async def test_list_quotes_filter(mcp_server, fake_jobber):
    fake_jobber.respond_to(
        "ListQuotes",
        {"quotes": {"nodes": [{"id": "q_1"}], "totalCount": 1, "pageInfo": {"hasNextPage": False}}},
    )
    async with Client(mcp_server) as c:
        await c.call_tool(
            "jobber_list_quotes",
            {"status": "APPROVED", "updated_after": "2026-01-01T00:00:00Z"},
        )
    variables = fake_jobber.calls[-1]["variables"]
    assert variables["filter"]["status"] == "APPROVED"
    assert variables["filter"]["updatedAfter"] == "2026-01-01T00:00:00Z"


async def test_get_quote(mcp_server, fake_jobber):
    fake_jobber.respond_to("GetQuote", {"quote": {"id": "q_9", "quoteNumber": "Q-9"}})
    async with Client(mcp_server) as c:
        result = await c.call_tool("jobber_get_quote", {"quote_id": "q_9"})
    assert _payload(result)["quote"]["quoteNumber"] == "Q-9"


async def test_create_note_on_quote(mcp_server, fake_jobber):
    fake_jobber.respond_to(
        "CreateNoteOnQuote",
        {"noteCreate": {"note": {"id": "n_1", "message": "hi"}, "userErrors": []}},
    )
    async with Client(mcp_server) as c:
        result = await c.call_tool(
            "jobber_create_note_on_quote",
            {"quote_id": "q_1", "body": "hi"},
        )
    data = _payload(result)
    assert data["ok"] is True
    assert data["note"]["message"] == "hi"


async def test_list_invoices_builds_date_filter(mcp_server, fake_jobber):
    fake_jobber.respond_to(
        "ListInvoices",
        {"invoices": {"nodes": [], "totalCount": 0, "pageInfo": {"hasNextPage": False}}},
    )
    async with Client(mcp_server) as c:
        await c.call_tool(
            "jobber_list_invoices",
            {"paid_status": "PAID", "date_from": "2026-01-01", "date_to": "2026-03-31"},
        )
    f = fake_jobber.calls[-1]["variables"]["filter"]
    assert f["invoiceStatus"] == "PAID"
    assert f["issuedAfter"] == "2026-01-01"
    assert f["issuedBefore"] == "2026-03-31"


async def test_list_jobs_filters(mcp_server, fake_jobber):
    fake_jobber.respond_to(
        "ListJobs",
        {"jobs": {"nodes": [{"id": "j_1"}], "totalCount": 1, "pageInfo": {"hasNextPage": False}}},
    )
    async with Client(mcp_server) as c:
        result = await c.call_tool(
            "jobber_list_jobs",
            {"status": "COMPLETED", "completed_after": "2026-03-01T00:00:00Z"},
        )
    assert _payload(result)["jobs"][0]["id"] == "j_1"
    f = fake_jobber.calls[-1]["variables"]["filter"]
    assert f == {"status": "COMPLETED", "completedAfter": "2026-03-01T00:00:00Z"}


async def test_search_partitions_results(mcp_server, fake_jobber):
    fake_jobber.respond_to(
        "GlobalSearch",
        {
            "clients": {"nodes": [{"id": "c_1"}]},
            "jobs": {"nodes": [{"id": "j_1"}]},
            "quotes": {"nodes": []},
            "invoices": {"nodes": [{"id": "i_1"}]},
        },
    )
    async with Client(mcp_server) as c:
        result = await c.call_tool("jobber_search", {"text": "roof"})
    data = _payload(result)
    assert data["clients"][0]["id"] == "c_1"
    assert data["quotes"] == []
    assert data["invoices"][0]["id"] == "i_1"
