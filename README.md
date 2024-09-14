# Listing of open-source for energy applications

(This is a work in progress - the resulting index will be published when available, so please keep an eye on this repository and tip the project about any resources that you are aware of)

The raw datasets are published here (nice layout has not been made yet):

- [Raw index](https://data.pierrevf.consulting/oss4energy/summary.toml)
- [Listing as CSV](https://data.pierrevf.consulting/oss4energy/listing_data.csv)


Other mapping initiatives that you may want to consider looking at (all the repositories that these linked to have been indexed here):

- https://landscape.lfenergy.org/
- https://opensustain.tech/

Sources of the data indexed are:

- https://landscape.lfenergy.org/
- https://opensustain.tech/
- Manually added references from the contributors


## What is the vision of this project, is it just yet another listing?

The vision is that this project should provide a list of open-source software for energy applications, which also provides insight on the following aspects, which are key to the success of open-source usage:

- maintenance
- security
- tech stack
- context data (who uses it, maintains it, ...)

All of this should be provided in a way that makes it easy to search and interface to (e.g. with a structured machine-readable registry).

However, in the current stage it is indeed not providing all of these features yet. Help is appreciated to get there (see [open issues](https://github.com/Pierre-VF/oss4energy/issues)).


## Installation

The installation is straightforward if you are used to Python.


You have 2 options:

1. Simple installation:
    Create a virtual environment with Python 3.12 (the code is not tested for previous versions). Then install the package:
    > pip install .

2. Development-oriented installation (with Poetry), which only works on Unix systems. Run the makefile command:
    > make install

It is highly recommended to operate with a Github token (which you can create [here](https://github.com/settings/tokens/new)) 
in order to avoid being blocked by Github's rate limit on the API. These are much lower for unauthenticated accounts.

Make sure to generate this token with permissions to access public repositories.

The token can be imported by generating a *.env* file in the root of your repository with the following content:

```bash
# This is your token generated here: https://github.com/settings/tokens/new
GITHUB_API_TOKEN="...[add your token here]..."

# You can adjust the position of the cache database here (leave to default if you don't need adjustment)
SQLITE_DB=".data/db.sqlite"

# If you want to enable publication of the data to FTP, you can also set these variables
EXPORT_FTP_URL=""
EXPORT_FTP_USER=""
EXPORT_FTP_PASSWORD=""
```

## Running the code

Once you have completed the steps above, you can run the following commands (only valid on Unix systems):

- To generate an output dataset:
    > make generate_listing
- To refresh the list of targets to be scraped:
    > make discover
- To export the datasets to FTP (using the credentials from the environment):
    > make publish

Note: the indexing is heavy and involves a series of web (and API) calls. A caching mechanism is therefore added in the implementation of the requests (with a simple SQLite database). This means that you might potentially end with a large file stored locally on your disk (currently under 500 Mb).

## Need new features or found a bug?

Please open an issue on the repository [here](https://github.com/Pierre-VF/oss4energy/issues).