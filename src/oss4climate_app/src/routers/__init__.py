from functools import lru_cache

import pandas as pd
from oss4climate.src.parsers.licenses import (
    licence_url_from_license_name,
)
from oss4climate.src.parsers.listings import ResourceListing

from oss4climate_app.src.config import FILE_INPUT_LISTINGS_INDEX


@lru_cache(maxsize=2)
def listing_credits_df() -> pd.DataFrame:
    list_of_listings = ResourceListing.from_json(FILE_INPUT_LISTINGS_INDEX)

    df = list_of_listings.to_dataframe()
    # Sorting listings by descending number of datasets (and requiring at least 10 targets to be credited)
    min_targets = 10

    for i, r in df.iterrows():
        if (not isinstance(r["license_url"], str)) or r["license_url"] == "NaN":
            df.loc[i, "license_url"] = licence_url_from_license_name(r["license"])

    df_no_nas = (
        df.dropna()
        .sort_values("target_count", ascending=False)
        .query(f"target_count>={min_targets}")
    )
    df_no_nas["target_count"] = df_no_nas["target_count"].astype(int)
    return df_no_nas
