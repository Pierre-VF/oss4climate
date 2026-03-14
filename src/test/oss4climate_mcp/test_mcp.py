import pytest
from fastmcp.client import Client
from oss4climate_mcp.main import mcp


@pytest.mark.asyncio
async def test_list_tools():
    async with Client(transport=mcp) as main_mcp_client:
        list_tools = await main_mcp_client.list_tools()
        list_resources = await main_mcp_client.list_resources()

        assert len(list_tools) > 0
        assert len(list_resources) > 0
