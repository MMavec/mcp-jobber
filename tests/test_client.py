"""GraphQL client tests: header wiring, error surfacing, rate-limit hooks."""

from __future__ import annotations

import pytest

from mcp_jobber.client import JobberGraphQLError


async def test_execute_sends_expected_headers_and_body(jobber_client, fake_jobber):
    fake_jobber.respond_to("GetClient", {"client": {"id": "c_1"}})
    data = await jobber_client.execute("query GetClient($id: EncodedId!) { client(id:$id) { id } }", {"id": "c_1"})

    assert data == {"client": {"id": "c_1"}}
    call = fake_jobber.calls[-1]
    assert call["variables"] == {"id": "c_1"}
    assert call["headers"]["authorization"].startswith("Bearer ")
    assert call["headers"]["x-jobber-graphql-version"]


async def test_graphql_errors_raise(jobber_client, fake_jobber):
    fake_jobber.respond_error("BrokenOp", [{"message": "bad field"}])
    with pytest.raises(JobberGraphQLError, match="bad field"):
        await jobber_client.execute("query BrokenOp { x }")


async def test_captures_cost_extension(jobber_client, fake_jobber):
    # `respond_to` doesn't support extensions, so stage raw via internal hook.
    fake_jobber._responses.setdefault("CostOp", []).append(
        {"data": {"ok": True}, "extensions": {"cost": {"requestedQueryCost": 12}}}
    )
    await jobber_client.execute("query CostOp { ok }")
    assert jobber_client.last_cost == {"requestedQueryCost": 12}
