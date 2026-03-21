import pytest
from fastmcp.client import Client
from oss4climate_app.src.mcp_server import ProjectDetails, mcp


@pytest.mark.asyncio
async def test_list_tools():
    async with Client(transport=mcp) as mcp_client:
        list_tools = await mcp_client.list_tools()
        list_resources = await mcp_client.list_resources()

        assert len(list_tools) > 0
        assert len(list_resources) >= 0

        r = await mcp_client.call_tool(
            "read_project_details", {"url": "https://github.com/Pierre-VF/oss4climate"}
        )
        # Check success of parsing
        ProjectDetails(**r.data.__dict__)

        n_max_results = 10
        rs_raw = await mcp_client.call_tool(
            "search_for_projects",
            {
                "topic": "oss4climate",
                "user_objective": "just testing",
                "n_max_results": n_max_results,
            },
        )
        # Check success of parsing
        rs = [ProjectDetails(**i.__dict__) for i in rs_raw.data]
        assert isinstance(rs, list)
        assert n_max_results >= len(rs) > 0
        for i in rs:
            assert isinstance(i, ProjectDetails)
