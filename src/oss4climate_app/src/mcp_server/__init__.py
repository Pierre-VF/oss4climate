"""
Example of an MCP server using https://github.com/modelcontextprotocol/python-sdk
"""

import pandas as pd
from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.exceptions import NotFoundError
from pydantic import BaseModel

from oss4climate_app.src.search import typesense_io

# Create an MCP server
mcp = FastMCP(
    "MCP supporting open-source project discovery in the sustainability field.",
)
_TS_CLIENT = typesense_io.generate_client()


class ProjectDetails(BaseModel):
    idx: str
    name: str
    description: str
    language: str
    url: str
    readme_preview: str | None = None
    license: str | None = None

    @staticmethod
    def from_typesense_item(r: typesense_io.ResultItem) -> "ProjectDetails":
        return ProjectDetails(
            idx=str(r.name),
            name=r.name,
            description=str(r.description),
            language=str(r.language),
            url=r.url,
            readme_preview=str(r.readme)[:2000],
            license=r.license,
        )

    @staticmethod
    def from_row(r: dict | pd.Series) -> "ProjectDetails":
        return ProjectDetails(
            idx=str(r["id"]),
            name=r["name"],
            description=str(r["description"]),
            language=str(r["language"]),
            url=r["url"],
            readme_preview=r["readme"][:2000],
        )


@mcp.tool()
def read_project_details(url: str) -> ProjectDetails:
    """Provides the details of a project for which the URL is provided.
    This is meant to provide you context about projects from Github, Gitlab, Bitbucket and other Gitx places.
    """
    res = typesense_io.search_for_url(_TS_CLIENT, url)
    r = [ProjectDetails.from_typesense_item(i) for i in res.results]
    if len(r) < 1:
        print(f"[read_project_details] url= {url} [NOT FOUND]")
        raise NotFoundError()
    else:
        print(f"[read_project_details] url= {url} [FOUND] ({len(r)} results)")
        return r[0]


@mcp.tool()
def search_for_projects(
    topic: str,
    user_objective: str,
    n_max_results: int = 50,
    ts_client=Depends(typesense_io.generate_client),
) -> list[ProjectDetails]:
    """Searches for projects that are related to a topic.
    `user_objective` is a string that explains what the user is trying to achieve.
    `n_max_results` is an integer that sets the maximum number of results returned"""

    res = typesense_io.search_with_query(
        ts_client,
        query=topic,
        results_per_page=n_max_results,
        page=1,
    )
    print(
        f"""[search] keywords= {topic} / {len(res.results)} results (max={n_max_results})
        User objective is: {user_objective}
        """
    )
    return [ProjectDetails.from_typesense_item(i) for i in res.results]


@mcp.prompt()
def search_prompt(topic: str):
    """Provides a prompt to guide the user in searching for a project"""
    return f"Tell me about 10 projects that address the topic of {topic}"


# Run with streamable HTTP transport
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
