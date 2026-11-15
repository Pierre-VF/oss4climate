"""
Oss4climate app
"""

from oss4x.app import app, mark_test_mode
from oss4x.app.src.config import FILE_OUTPUT_LISTING_FEATHER
from oss4x.app.src.mcp_server import mcp

# To support imports in other modules (as a one-stop-shop)
__all__ = ["FILE_OUTPUT_LISTING_FEATHER", "app", "mark_test_mode", "mcp"]
