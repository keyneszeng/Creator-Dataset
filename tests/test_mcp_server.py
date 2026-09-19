import json
import pytest
from mcp import Client

import app.mcp_server as mcp_module


class FakeAgentService:
    def account_status(self):
        return {
            "role": "member",
            "mode": "free",
            "unlimited": True,
        }

    def creator_submit(self, url: str, *, max_pages: int = 20):
        return {
            "creator_id": "creator-1",
            "status": "PENDING",
            "import_job_id": 1,
        }

    def creator_status(self, creator_id: str):
        return {
            "creator_id": creator_id,
            "status": "COMPLETE",
            "discovered_posts": 2,
            "job_id": 1,
            "error": None,
        }

    def creator_posts(self, creator_id: str, *, limit: int, offset: int):
        return {
            "creator_id": creator_id,
            "total": 1,
            "offset": offset,
            "items": [],
        }

    def dataset_prepare(self, post_id: str):
        return {
            "post_id": post_id,
            "status": "PREPARING",
            "free": True,
            "generation_job_id": 1,
        }

    def dataset_status(self, post_id: str):
        return {"post_id": post_id, "ready": False, "status": "PENDING"}

    def dataset_get(self, post_id: str):
        return {"post_id": post_id, "ready": True, "summary": "summary"}

    def dataset_content(
        self,
        post_id: str,
        *,
        max_text_units: int,
        max_comments: int,
    ):
        return {"post_id": post_id, "ready": True, "text_units": []}

    def dataset_comments(
        self,
        post_id: str,
        *,
        offset: int,
        limit: int,
    ):
        return {"post_id": post_id, "total": 0, "items": []}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_tools_are_compact_and_callable(monkeypatch) -> None:
    fake = FakeAgentService()
    monkeypatch.setattr(mcp_module, "_service", lambda: fake)

    async with Client(
        mcp_module.mcp,
        raise_exceptions=True,
    ) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}

        assert names == {
            "account_status",
            "creator_submit",
            "creator_status",
            "creator_posts",
            "dataset_prepare",
            "dataset_status",
            "dataset_get",
            "dataset_content",
            "dataset_comments",
        }

        account = await client.call_tool("account_status", {})
        account_payload = json.loads(account.content[0].text)
        assert account_payload["mode"] == "free"

        prepared = await client.call_tool(
            "dataset_prepare",
            {"post_id": "post-1"},
        )
        prepared_payload = json.loads(prepared.content[0].text)
        assert prepared_payload["status"] == "PREPARING"
        assert prepared_payload["free"] is True
