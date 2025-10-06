"""
Analysis of the OSS.tech landscape
"""

import os
import os.path
import sys
from datetime import timedelta
from urllib.parse import urlparse
from urllib.request import urlretrieve

import matplotlib.pyplot as plt
import pandas as pd

from oss4climate.src.parsers.git_platforms.github_io import GithubScraper

DATA_FOLDER = ".data"
RESULTS_FOLDER = f"{DATA_FOLDER}/results"

PROJECT_XLSX = f"{DATA_FOLDER}/projects.xlsx"
ORGANISATIONS_XLSX = f"{DATA_FOLDER}/organisations.xlsx"
FUNDING_XLSX = f"{DATA_FOLDER}/funding.xlsx"
LOG_FILE = f"{RESULTS_FOLDER}/log.txt"

funding_xlsx_url = r"https://api.getgrist.com/o/docs/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/download/xlsx?viewSection=17&tableId=Funding&activeSortSpec=%5B%5D&filters=%5B%5D&linkingFilter=%7B%22filters%22%3A%7B%7D%2C%22operations%22%3A%7B%7D%7D"
organisations_xlsx_url = r"https://api.getgrist.com/o/docs/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/download/xlsx?viewSection=7&tableId=Organizations&activeSortSpec=%5B-156%5D&filters=%5B%7B%22colRef%22%3A124%2C%22filter%22%3A%22%7B%5C%22excluded%5C%22%3A%5B%5D%7D%22%7D%5D&linkingFilter=%7B%22filters%22%3A%7B%7D%2C%22operations%22%3A%7B%7D%7D"
projects_xlsx_url = r"https://api.getgrist.com/o/docs/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/download/xlsx?viewSection=5&tableId=Projects&activeSortSpec=%5B132%5D&filters=%5B%5D&linkingFilter=%7B%22filters%22%3A%7B%7D%2C%22operations%22%3A%7B%7D%7D"

# Ensuring folders exist
for i in [DATA_FOLDER, RESULTS_FOLDER]:
    if not os.path.exists(i):
        os.makedirs(i, exist_ok=True)

file_out = open(LOG_FILE, "w")
sys.stdout = file_out

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
    fig_size: tuple[int, int] = (12, 6),
    yaxis_title: str = "Number of projects",
    xaxis_title: str | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=fig_size)
    if order:
        x_sorted = x.sort_values(ascending=False)
    else:
        x_sorted = x.copy()
    x_sorted.index = [str(i) for i in x_sorted.index.to_list()]
    idx = x_sorted.index.to_list()
    ax.bar(x=idx, height=x_sorted)
    if x_ticks_vertical:
        ax.set_xticks(idx, idx, rotation="vertical")
    ax.set_ylabel(yaxis_title)
    if xaxis_title:
        ax.set_xlabel(xaxis_title)
    try:
        fig.tight_layout()
    except Exception as e:
        print(f"Failed figure layout tightening {path_out} ({e})")
    try:
        fig.savefig(path_out)
    except Exception as e:
        print(f"Failed figure export {path_out} ({e})")


def plot_pie(
    x: pd.Series,
    path_out: str,
    fig_size: tuple[int, int] = (14, 6),
) -> None:
    fig, ax = plt.subplots(figsize=fig_size)
    ax.pie(
        x,
        labels=x.index,
        # radius=3,
        # center=(4, 4),
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
df_projects_augmented["count"] = 1


n_projects = len(df_projects_augmented)

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
[
    print(f"- {k} : {v} projects ({100 * v / n_projects:.1f} % of total)")
    for k, v in ecosystem_size.items()
]
print(" ")

plot_histogram(
    pd.Series(list(ecosystem_size.values()), index=list(ecosystem_size.keys())).astype(
        int
    ),
    path_out=f"{RESULTS_FOLDER}/ecosystems.png",
    x_ticks_vertical=True,
    order=True,
    xaxis_title="Ecosystem",
)


# Which projects use which language?
projects_by_language = {}
unique_languages = df_projects_augmented["language"].unique()
for e in list(unique_languages):
    repos_e = []
    for i, r in df_projects_augmented.iterrows():
        if e == str(r["language"]):
            repos_e.append(dict(r))
    if str(e) == "nan":
        e = "(Undefined)"
    projects_by_language[e] = repos_e
print("Repos per language:")
language_size = {k: len(v) for k, v in projects_by_language.items()}
[
    print(f"- {k} : {v} projects ({100 * v / n_projects:.1f} % of total)")
    for k, v in language_size.items()
]
print(" ")
plot_histogram(
    pd.Series(list(language_size.values()), index=list(language_size.keys())).astype(
        int
    ),
    path_out=f"{RESULTS_FOLDER}/languages.png",
    x_ticks_vertical=True,
    order=True,
    xaxis_title="Programming language",
)

# Which projects are funded?
funded_projects = df_projects_augmented.loc[
    df_projects_augmented["augmented_is_funded"] == True, :
].copy()

n_funded = len(funded_projects)
n_unfunded = len(df_projects_augmented) - n_funded

plot_pie(
    pd.Series([n_funded, n_unfunded], index=["Funding enabled", "Unfunded"]),
    path_out=f"{RESULTS_FOLDER}/funding.png",
)


# Pie charts per something
def _pie_plot_per_something(dfx: pd.DataFrame, col: str, path_out: str):
    all_x = dfx[col].unique().tolist()
    projects_per_something = {k: len(dfx[dfx[col] == k]) for k in all_x}
    plot_pie(
        pd.Series(
            list(projects_per_something.values()),
            index=list(projects_per_something.keys()),
        ),
        path_out=path_out,
    )


# Projects per section
_pie_plot_per_something(
    df_projects_augmented, col="category", path_out=f"{RESULTS_FOLDER}/per_category.png"
)
_pie_plot_per_something(
    df_projects_augmented, col="platform", path_out=f"{RESULTS_FOLDER}/per_platform.png"
)

# Contributors per project
df_projects_by_contributors = (
    df_projects_augmented.loc[:, ["count", "contributors"]]
    .groupby("contributors")
    .sum()
).reset_index()


def _f_cat(x: int) -> str:
    if x < 5:
        return str(int(x))
    elif x <= 10:
        return "5-10"
    elif x <= 20:
        return "11-20"
    elif x <= 50:
        return "21-50"
    elif x <= 100:
        return "51-100"
    else:
        return ">100"


df_projects_by_contributors["contributors_2"] = df_projects_by_contributors.index
df_projects_by_contributors["contributors_cat"] = df_projects_by_contributors[
    "contributors_2"
].apply(_f_cat)
s_contributors = (
    df_projects_by_contributors.loc[:, ["count", "contributors_cat"]]
    .groupby("contributors_cat")
    .sum()
)["count"]

plot_histogram(
    s_contributors.loc[
        [
            "1",
            "2",
            "3",
            "4",
            "5-10",
            "11-20",
            "21-50",
            "51-100",
            ">100",
        ]
    ],
    path_out=f"{RESULTS_FOLDER}/per_contributors.png",
    x_ticks_vertical=False,
    order=False,
    xaxis_title="Number of contributors",
    # fig_size=(20, 6),
)

# -----------------------------------------------------------------------------------
# Analysis of PRs and activity of OSST
# -----------------------------------------------------------------------------------
url = "https://github.com/protontypes/open-sustainable-technology"
ghs = GithubScraper(cache_lifetime=timedelta(days=1))
prs = ghs.fetch_pull_requests(url, open_only=False)

n_total_prs = len(prs)
n_accepted_prs = 0
approval_times = []
users = pd.Series([i.user_id for i in prs])

for i in prs:
    if i.accepted:
        n_accepted_prs += 1
        approval_times.append(i.approval_time)

print(f"Percentage of approvals: {(100 * n_accepted_prs / n_total_prs):.1f}")
print(f"Number of users having opened PRs: {len(users.unique())}")

df_approvals = pd.Series(approval_times).to_frame("duration")
df_approvals["count"] = 1


def _td_to_days(td, _round: bool = False) -> float | str:
    out = td.seconds / (3600 * 24) + td.days
    if _round:
        if out < 1:
            out = "<1"
        elif out < 2:
            out = "1-2"
        elif out < 3:
            out = "2-3"
        elif out < 7:
            out = "3-7"
        elif out < 14:
            out = "7-14"
        elif out < 28:
            out = "14-28"
        elif out <= 60:
            out = "28-60"
        elif out > 60:
            out = ">60"
    return out


t_app = df_approvals["duration"]
print(f"Mean approval time: {_td_to_days(t_app.mean()):.1f} days")
print(f"Median approval time: {_td_to_days(t_app.median()):.1f} days")
print(f"75% approval time: {_td_to_days(t_app.quantile(0.75)):.1f} days")
print(f"Max approval time: {_td_to_days(t_app.max()):.1f} days")

df_approvals["days"] = df_approvals["duration"].apply(
    lambda x: _td_to_days(x, _round=True)
)
s_approval_times_days = df_approvals[["days", "count"]].groupby("days").sum()["count"]

plot_histogram(
    s_approval_times_days.loc[
        ["<1", "1-2", "2-3", "3-7", "7-14", "14-28", "28-60", ">60"]
    ],
    path_out=f"{RESULTS_FOLDER}/osst_approval_time.png",
    xaxis_title="Days to approve PR",
    yaxis_title="Number of PRs",
    order=False,
    fig_size=(1200, 500),
)

df_prs_per_user = (
    pd.DataFrame(data={"user_id": [i.user_id for i in prs], "count": 1})
    .groupby("user_id")
    .sum()
)

df_prs_per_user_simpler = df_prs_per_user.reset_index()
df_prs_per_user_simpler.loc[df_prs_per_user_simpler["count"] < 5, "user_id"] = (
    "(Others)"
)

plot_histogram(
    df_prs_per_user_simpler.groupby("user_id").sum()["count"],
    path_out=f"{RESULTS_FOLDER}/osst_prs_per_user.png",
    xaxis_title="User",
    yaxis_title="Number of PRs",
    x_ticks_vertical=True,
    order=True,
)


# End

# Closing file output
file_out.close()


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
