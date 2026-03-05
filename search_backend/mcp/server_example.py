"""
Example of an MCP server using https://github.com/modelcontextprotocol/python-sdk
"""

import typesense
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from typesense.types.document import (
    SearchParameters,
)

API_KEY = "12345"

client = typesense.Client(
    {
        "nodes": [
            {
                "host": "localhost",
                "port": "8108",
                "protocol": "http",
            }
        ],
        "api_key": API_KEY,
        "connection_timeout_seconds": 2,
    }
)

# Dummy search to make sure it's running
client.collections["projects"].documents.search(
    {"q": "solar", "query_by": "description", "sort_by": "idx:asc"}
)
print(" ")
print("DUMMY SEARCH SUCCESSFUL")
print(" ")

# Create an MCP server
mcp_server = FastMCP(
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


@mcp_server.resource("resource://project/{url}")
def read_project_details(url: str) -> ProjectDetails:
    """Provides the details of a project for which the URL is provided.
    This is meant to provide you context about projects from Github, Gitlab, Bitbucket and other Gitx places."""

    print(f"[resource] project for {url}")
    results = client.collections["projects"].documents.search(
        SearchParameters(
            q=url,
            query_by="url",
            # For hybrid search
            # rerank_hybrid_matches=True,
            # vector_query="embedding_description:([], k: 200)",  # Here, reduce the relevant fields
            # sort_by="idx:asc",
            exclude_fields="embedding_description",
            per_page=20,
            page=1,
        )
    )
    hits = results["hits"]
    if len(hits) < 1:
        return ProjectDetails(id=0, idx=0, name="", description="", language="", url="")
    else:
        return ProjectDetails(**hits[0])


@mcp_server.resource("resource://known-projects")
def list_known_projects() -> list[ProjectDetails]:
    """List all known projects"""
    print("[list] LIST")

    results = client.collections["projects"].documents.search(
        SearchParameters(
            q="http",
            query_by="url",
            sort_by="idx:asc",
            exclude_fields="embedding_description",
            per_page=20,
            page=1,
        )
    )
    return [ProjectDetails(**r) for r in results["hits"]]


if False:

    @mcp_server.tool()
    def search_for_projects(topic: str) -> list[ProjectDetails]:
        """Searches for projects that are related to a topic"""
        print(f"[search] query = {topic}")

        results = client.collections[
            "projects"
        ].documents.search(
            SearchParameters(
                q=topic,
                query_by="embedding_description, name",
                # For hybrid search
                # rerank_hybrid_matches=True,
                vector_query="embedding_description:([], k: 200)",  # Here, reduce the relevant fields
                # sort_by="idx:asc",
                exclude_fields="embedding_description",
                per_page=20,
                page=1,
            )
        )
        return [ProjectDetails(**r) for r in results["hits"]]


# Run with streamable HTTP transport
if __name__ == "__main__":
    mcp_server.run(transport="streamable-http")
