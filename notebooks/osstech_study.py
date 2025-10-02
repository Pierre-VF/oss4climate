"""
Analysis of the OSS.tech landscape
"""

import os
import os.path
from urllib.request import urlretrieve

import pandas as pd

DATA_FOLDER = ".data"

PROJECT_XLSX = f"{DATA_FOLDER}/projects.xlsx"
ORGANISATIONS_XLSX = f"{DATA_FOLDER}/organisations.xlsx"
FUNDING_XLSX = f"{DATA_FOLDER}/funding.xlsx"

funding_xlsx_url = r"https://api.getgrist.com/o/docs/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/download/xlsx?viewSection=17&tableId=Funding&activeSortSpec=%5B%5D&filters=%5B%5D&linkingFilter=%7B%22filters%22%3A%7B%7D%2C%22operations%22%3A%7B%7D%7D"
organisations_xlsx_url = r"https://api.getgrist.com/o/docs/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/download/xlsx?viewSection=7&tableId=Organizations&activeSortSpec=%5B-156%5D&filters=%5B%7B%22colRef%22%3A124%2C%22filter%22%3A%22%7B%5C%22excluded%5C%22%3A%5B%5D%7D%22%7D%5D&linkingFilter=%7B%22filters%22%3A%7B%7D%2C%22operations%22%3A%7B%7D%7D"
projects_xlsx_url = r"https://api.getgrist.com/o/docs/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/download/xlsx?viewSection=5&tableId=Projects&activeSortSpec=%5B132%5D&filters=%5B%5D&linkingFilter=%7B%22filters%22%3A%7B%7D%2C%22operations%22%3A%7B%7D%7D"

# ------------------------------------------------------------------------------------
# Step 1 : Download files if missing
# ------------------------------------------------------------------------------------
print("Downloading files")
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER, exist_ok=True)


def _f_download_if_missing(url: str, target: str) -> None:
    if not os.path.exists(target):
        urlretrieve(url, target)


_f_download_if_missing(projects_xlsx_url, PROJECT_XLSX)
_f_download_if_missing(organisations_xlsx_url, ORGANISATIONS_XLSX)
_f_download_if_missing(funding_xlsx_url, FUNDING_XLSX)
print("> Download complete")
print(" ")

# ------------------------------------------------------------------------------------
# Step 2: Loading into pandas
# ------------------------------------------------------------------------------------
print("Loading data into python")

df_projects = pd.read_excel(PROJECT_XLSX)
df_organisations = pd.read_excel(ORGANISATIONS_XLSX)
df_funding = pd.read_excel(FUNDING_XLSX)

print("> Loading complete")
print(" ")
