"""
FastAPI app to operate a search

Note: heavily inspired from https://github.com/alexmolas/microsearch/
"""

from uvicorn import run

try:
    from src.app import app
except ImportError:
    from .src.app import app

if __name__ == "__main__":
    # For local testing
    run(app, host="127.0.0.1", port=8080)
