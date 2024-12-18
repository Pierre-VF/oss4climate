"""
FastAPI app to operate a search

Note: heavily inspired from https://github.com/alexmolas/microsearch/
"""

from uvicorn import run

try:
    from oss4climate_app import app
except ImportError:
    # For legacy usage compatibility
    from src.oss4climate_app import app

if __name__ == "__main__":
    # For local testing
    from oss4climate_app import mark_test_mode

    mark_test_mode()
    run(app, host="127.0.0.1", port=8080)
