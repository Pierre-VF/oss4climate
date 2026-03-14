"""
Example of an MCP server using https://github.com/modelcontextprotocol/python-sdk
"""

import pandas as pd
from mcp.server.fastmcp import FastMCP
from oss4climate.src.config import SETTINGS
from pydantic import BaseModel

# Full indexing of the files
df = pd.read_feather(
    SETTINGS.get_listing_file_with_readme_and_description_file_columns()[0]
)
df["idx"] = df.index.to_series().astype(int)

# Create an MCP server
mcp = FastMCP(
    "MCP for project data",
    json_response=True,
    # stateless_http=True,
)


class ProjectDetails(BaseModel):
    id: int
    idx: int
    name: str
    description: str
    language: str
    url: str


@mcp.resource("resource://project/{url}")
def read_project_details(url: str) -> ProjectDetails:
    """Provides the details of a project for which the URL is provided.
    This is meant to provide you context about projects from Github, Gitlab, Bitbucket and other Gitx places."""
    return ProjectDetails(id=0, idx=0, name="", description="", language="", url="")


@mcp.resource("resource://known-projects")
def list_known_projects() -> list[ProjectDetails]:
    """List all known projects"""
    print("[list] LIST")
    return []


@mcp.tool()
def search_for_projects(topic: str) -> list[ProjectDetails]:
    """Searches for projects that are related to a topic"""
    print(f"[search] query = {topic}")

    return []


# Run with streamable HTTP transport
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
