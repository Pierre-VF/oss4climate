"""
Analysis of the OSS.tech landscape
"""

import os
import os.path
from urllib.parse import urlparse
from urllib.request import urlretrieve

import matplotlib.pyplot as plt
import pandas as pd

DATA_FOLDER = ".data"
RESULTS_FOLDER = f"{DATA_FOLDER}/results"

PROJECT_XLSX = f"{DATA_FOLDER}/projects.xlsx"
ORGANISATIONS_XLSX = f"{DATA_FOLDER}/organisations.xlsx"
FUNDING_XLSX = f"{DATA_FOLDER}/funding.xlsx"

funding_xlsx_url = r"https://api.getgrist.com/o/docs/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/download/xlsx?viewSection=17&tableId=Funding&activeSortSpec=%5B%5D&filters=%5B%5D&linkingFilter=%7B%22filters%22%3A%7B%7D%2C%22operations%22%3A%7B%7D%7D"
organisations_xlsx_url = r"https://api.getgrist.com/o/docs/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/download/xlsx?viewSection=7&tableId=Organizations&activeSortSpec=%5B-156%5D&filters=%5B%7B%22colRef%22%3A124%2C%22filter%22%3A%22%7B%5C%22excluded%5C%22%3A%5B%5D%7D%22%7D%5D&linkingFilter=%7B%22filters%22%3A%7B%7D%2C%22operations%22%3A%7B%7D%7D"
projects_xlsx_url = r"https://api.getgrist.com/o/docs/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/download/xlsx?viewSection=5&tableId=Projects&activeSortSpec=%5B132%5D&filters=%5B%5D&linkingFilter=%7B%22filters%22%3A%7B%7D%2C%22operations%22%3A%7B%7D%7D"

# Ensuring folders exist
for i in [DATA_FOLDER, RESULTS_FOLDER]:
    if not os.path.exists(i):
        os.makedirs(i, exist_ok=True)

# ------------------------------------------------------------------------------------
# Step 1 : Download files if missing
# ------------------------------------------------------------------------------------
print("Downloading files")


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

# ------------------------------------------------------------------------------------
# Step 3: Looking at Richard's questions
# ------------------------------------------------------------------------------------


# Plotting functions
def plot_histogram(
    x: pd.Series,
    path_out: str,
    x_ticks_vertical: bool = True,
    order: bool = True,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    if order:
        x_sorted = x.sort_values(ascending=False)
    else:
        x_sorted = x.copy()
    x_sorted.index = [str(i) for i in x_sorted.index.to_list()]
    idx = x_sorted.index.to_list()
    ax.bar(x=idx, height=x_sorted)
    if x_ticks_vertical:
        ax.set_xticks(idx, idx, rotation="vertical")
    fig.tight_layout()
    fig.savefig(path_out)


def plot_pie(
    x: pd.Series,
    path_out: str,
) -> None:
    fig, ax = plt.subplots()
    ax.pie(
        x,
        labels=x.index,
        radius=3,
        center=(4, 4),
        # wedgeprops={"linewidth": 1, "edgecolor": "white"},
        # frame=True,
    )
    fig.tight_layout()
    fig.savefig(path_out)


df_projects_augmented = df_projects.copy()
df_projects_augmented["augmented_ecosystems"] = df_projects_augmented[
    "ecosystems"
].apply(lambda x: [i.strip() for i in str(x).split(";")])
df_projects_augmented["augmented_is_funded"] = (
    df_projects_augmented["funding_links"].astype(str) != "nan"
)
df_projects_augmented["augmented_funded_through"] = df_projects_augmented[
    "funding_links"
].apply(lambda x: urlparse(x).netloc if str(x) != "nan" else "")

# What are the ecosystems?
all_ecosystems = []
for i in df_projects_augmented["augmented_ecosystems"].to_list():
    all_ecosystems += i
unique_ecosystems = pd.Series(all_ecosystems).unique()
unique_ecosystems.sort()
print(f"Ecosystems: {unique_ecosystems}")


# Which projects appear in which ecosystem?
projects_by_ecosystem = {}
for e in list(unique_ecosystems):
    if e == "nan":
        continue
    repos_e = []
    for i, r in df_projects_augmented.iterrows():
        if e in r["augmented_ecosystems"]:
            repos_e.append(dict(r))
    projects_by_ecosystem[e] = repos_e
print("Repos per ecosystem:")
ecosystem_size = {k: len(v) for k, v in projects_by_ecosystem.items()}
[print(f"- {k} : {v} projects") for k, v in ecosystem_size.items()]
print(" ")

plot_histogram(
    pd.Series(list(ecosystem_size.values()), index=list(ecosystem_size.keys())).astype(
        int
    ),
    path_out=f"{RESULTS_FOLDER}/ecosystems.png",
    x_ticks_vertical=True,
    order=True,
)


# Which projects use which language?
projects_by_language = {}
unique_languages = df_projects_augmented["language"].unique()
for e in list(unique_languages):
    if e == "nan":
        continue
    repos_e = []
    for i, r in df_projects_augmented.iterrows():
        if e == r["language"]:
            repos_e.append(dict(r))
    projects_by_language[e] = repos_e
print("Repos per language:")
language_size = {k: len(v) for k, v in projects_by_language.items()}
[print(f"- {k} : {v} projects") for k, v in language_size.items()]
print(" ")
plot_histogram(
    pd.Series(list(language_size.values()), index=list(language_size.keys())).astype(
        int
    ),
    path_out=f"{RESULTS_FOLDER}/languages.png",
    x_ticks_vertical=True,
    order=True,
)

# Which projects are funded?
funded_projects = df_projects_augmented.loc[
    df_projects_augmented["augmented_is_funded"] == True, :
].copy()

n_funded = len(funded_projects)
n_unfunded = len(df_projects_augmented) - n_funded

plot_pie(
    pd.Series([n_funded, n_unfunded], index=["Funded", "Unfunded"]),
    path_out=f"{RESULTS_FOLDER}/funding.png",
)

# Contributors per project


"""
- Transitive dependencies of the datasets (how many other projects are using it?)
- How long does it take for a project to get through? (PR opening to validation)
- How many contributions to OSS tech are accepted?
- Graph:
	- Breakdown of projects
		- by ecosystems
		- by language
		- number of contributors
		- how many are funded (having a funding statement)

Richard's questions:
Get numbers for how many projects
Talk about methodology for finding projects
Talk about citations and usage of projects
Talk about different fields
Talk about downstream projects -> climatetriage, openclimate.fund
Discussion of how this is useful?
Number of contributors to OST
Governance?
Communicating in academic settings
Structuring the data
Condensing the dataset into a format that is easy to process
"""
