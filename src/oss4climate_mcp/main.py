"""
Example of an MCP server using https://github.com/modelcontextprotocol/python-sdk
"""

import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import NotFoundError
from oss4climate.src.config import SETTINGS
from pydantic import BaseModel

# Full indexing of the files
df: pd.DataFrame = pd.read_feather(
    SETTINGS.get_listing_file_with_readme_and_description_file_columns()[0]
)
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
    keywords = topic.split(" ")
    res = df[df["readme"].apply(lambda x: any([(i in x) for i in keywords]))].head(
        n_max_results
    )
    print(f"[search] keywords= {keywords} / {len(res)} results (max={n_max_results})")
    print(res[["url", "name"]])
    return [ProjectDetails.from_row(i) for _, i in res.iterrows()]


# Run with streamable HTTP transport
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
