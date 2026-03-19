"""
Example of an MCP server using https://github.com/modelcontextprotocol/python-sdk
"""

import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import NotFoundError
from pydantic import BaseModel

from oss4climate.src.config import FILE_OUTPUT_LISTING_FEATHER
from oss4climate.src.database.projects import project_dataframe_loader
from oss4climate_app.src.search import typesense_io

# Full indexing of the files
df: pd.DataFrame = project_dataframe_loader(FILE_OUTPUT_LISTING_FEATHER)
df["idx"] = df.index.to_series().astype(int)

# Create an MCP server
mcp = FastMCP(
    "MCP supporting open-source project discovery in the sustainability field.",
)


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
    r = df[df["url"] == url]
    if len(r) < 1:
        print(f"[read_project_details] url= {url} [NOT FOUND]")
        raise NotFoundError()
    else:
        print(f"[read_project_details] url= {url} [FOUND]")
        return ProjectDetails.from_row(r.iloc[0])


@mcp.tool()
def search_for_projects(topic: str, n_max_results: int = 50) -> list[ProjectDetails]:
    """Searches for projects that are related to a topic.
    `n_max_results` is an integer that sets the maximum number of results returned"""

    res = typesense_io.search_in_typesense(
        query=topic,
        results_per_page=n_max_results,
        page=1,
    )
    print(
        f"[search] keywords= {topic} / {len(res.results)} results (max={n_max_results})"
    )
    return [ProjectDetails.from_typesense_item(i) for i in res.results]


@mcp.prompt()
def search_prompt(topic: str):
    """Provides a prompt to guide the user in searching for a project"""
    return f"Tell me about 10 projects that address the topic of {topic}"


# Run with streamable HTTP transport
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
