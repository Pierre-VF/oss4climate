"""
Module containing the models and enums for the mapping
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class EnumDocumentationFileType(Enum):
    MARKDOWN = "md"
    RESTRUCTURED_TEXT = "rst"
    HTML = "html"
    UNKNOWN = "?"

    def from_filename(f: str) -> "EnumDocumentationFileType":
        f_lower = f.lower()
        if f_lower.endswith(".md"):
            return EnumDocumentationFileType.MARKDOWN
        elif f_lower.endswith(".rst"):
            return EnumDocumentationFileType.RESTRUCTURED_TEXT
        elif f_lower.endswith(".html"):
            return EnumDocumentationFileType.HTML
        else:
            return EnumDocumentationFileType.UNKNOWN


class ProjectDetails(BaseModel):
    id: str
    name: str
    organisation: Optional[str]
    url: str
    website: Optional[str]
    description: Optional[str]
    license: Optional[str]
    latest_update: Optional[date]
    language: Optional[str]
    last_commit: Optional[date]
    open_pull_requests: Optional[int]
    raw_details: Optional[dict]
    master_branch: Optional[str]
    readme: Optional[str]
    is_fork: Optional[bool]
    forked_from: Optional[str]
    readme_type: EnumDocumentationFileType = EnumDocumentationFileType.UNKNOWN
