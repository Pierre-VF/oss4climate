from oss4climate.src.config import SETTINGS

# Link to all documents
FILE_INPUT_INDEX = "indexes/repositories.toml"
FILE_INPUT_LISTINGS_INDEX = "indexes/listings.json"
FILE_OUTPUT_DIR = SETTINGS.LOCAL_FOLDER
FILE_OUTPUT_LISTING_FEATHER = f"{FILE_OUTPUT_DIR}/listing_data.feather"
FILE_OUTPUT_SUMMARY_TOML = f"{FILE_OUTPUT_DIR}/summary.toml"


# For data hosted outside of Github
URL_BASE = "https://data.pierrevf.consulting/oss4climate"
URL_RAW_INDEX = f"{URL_BASE}/summary.toml"
URL_LISTING_FEATHER = f"{URL_BASE}/listing_data.feather"
