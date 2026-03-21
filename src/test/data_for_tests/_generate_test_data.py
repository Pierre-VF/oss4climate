from pathlib import Path

import pandas as pd
from oss4climate.src.database.projects import project_dataframe_loader
from oss4climate_app.src.config import FILE_OUTPUT_LISTING_FEATHER

# Full indexing of the files
df: pd.DataFrame = project_dataframe_loader(FILE_OUTPUT_LISTING_FEATHER)

df_light = df[df["url"] == "https://github.com/Pierre-VF/oss4climate"]
df_light["readme"] = df_light["readme"].apply(
    lambda x: x[:500].replace("\n", " ").replace(",", " ")
)

df_light.to_csv(str(Path(__file__).parent / "listing.csv"))
