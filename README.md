# Listing of open-source for climate and energy applications

TLDR; if you're just looking for the search engine, you will find it here: https://oss4climate.pierrevf.consulting/ .


## What is the vision of this project, is it just yet another listing?

The vision is that this project should provide a list of open-source software for energy and climate applications, which also provides insight on the following aspects, which are key to the success of open-source usage:

- maintenance
- security
- tech stack
- context data (who uses it, maintains it, ...)


All of this should be provided in a way that makes it easy to search and interface to (e.g. with a structured machine-readable registry).

However, in the current stage it is indeed not providing all of these features yet. Help is appreciated to get there (see [open issues](https://github.com/Pierre-VF/oss4climate/issues)).

## Do you just want to carry out a search for open-source matching your needs?

To carry out a search without installing anything, you can just use the **web-app** here: https://oss4climate.pierrevf.consulting/ 

## What is the license of the code and the data?

The **code is licensed under an MIT license**, as the aim is to make it reusable by anyone.

The underlying listing data comes from a variety of repositories, some of which have a creative common licence. **That means that while you are free to reuse and adapt the software, there are restrictions on the usage of the listings data below.** Having noted this, the listing data can be downloaded as [TOML](https://data.pierrevf.consulting/oss4climate/summary.toml), [CSV](https://data.pierrevf.consulting/oss4climate/listing_data.csv) or [Feather (for Python pandas)](https://data.pierrevf.consulting/oss4climate/listing_data.feather).


## Where is the data coming from?

Input to the discovery process are given in the files in the **indexes** folder (you are welcome to add your own contribution):

- the listings scraped are listed in **[listings.toml](indexes/listings.toml)** (if you are interested in project listings, you should check all URLs in this file)
- repositories found in the listings and added manually are found in **[repositories.toml](indexes/repositories.toml)**  
- the associated scrapers in the folder **"src/oss4climate/src/parsers"**


The following projects are credited as major contributors to the underlying dataset:

- [OpenSustain.tech](https://opensustain.tech/) (who kindly licensed their dataset under *Creative Commons Attribution 4.0 International*)

- (... list in progress ...)


## Development and contribution

### Installation

Installation

The installation is straightforward if you are used to Python.


You have 2 options:

1. Simple installation:
    Create a virtual environment with Python 3.12 (the code is not tested for previous versions). Then install the package:
    > pip install .

2. Development-oriented installation (with Poetry), which only works on Unix systems. Run the makefile command:
    > make install

It is highly recommended to operate with a Github token (which you can create [here](https://github.com/settings/tokens/new)) 
in order to avoid being blocked by Github's rate limit on the API. The same consideration applies to Gitlab (token generation [here](https://gitlab.com/-/user_settings/personal_access_tokens)). These are much lower for unauthenticated accounts.

Make sure to generate this token with permissions to access public repositories.

The token can be imported by generating a *.env* file in the root of your repository with the following content:

```bash
# This is your token generated here: https://github.com/settings/tokens/new
GITHUB_API_TOKEN="...[add your token here]..."
# This is your token generated here: https://gitlab.com/-/user_settings/personal_access_tokens
GITLAB_ACCESS_TOKEN="...[add your token here]..."

# For app operation, a key to refresh the data (to avoid undesirable refreshing)
DATA_REFRESH_KEY="...[add a random key here]..."

# You can adjust the position of the cache database here (leave to default if you don't need adjustment)
SQLITE_DB=".data/db.sqlite"

# If you want to enable publication of the data to FTP, you can also set these variables
EXPORT_FTP_URL=""
EXPORT_FTP_USER=""
EXPORT_FTP_PASSWORD=""
```

### Running the code

Once you have completed the steps above, you can run the following commands (only valid on Unix systems):

Typical use-cases:

- To download the dataset:
    > make download_data
- To search in CLI mode (note that this is a very basic CLI):
    > make search


Advanced use-cases (to regenerate listings - avoid unless necessary, as this very resource intensive)

- To generate an output dataset:
    > make generate_listing
- To add new resources:
    > make add
- To refresh the list of targets to be scraped:
    > make discover
- To export the datasets to FTP (using the credentials from the environment):
    > make publish

Note: the indexing is heavy and involves a series of web (and API) calls. A caching mechanism is therefore added in the implementation of the requests (with a simple SQLite database). This means that you might potentially end with a large file stored locally on your disk (currently under 500 Mb).

## Need new features or found a bug?

Please open an issue on the repository [here](https://github.com/Pierre-VF/oss4climate/issues).

If you have a use-case that you would like to develop based upon this, or need new features, please get in touch with [PierreVF Consulting](https://www.pierrevf.consulting/) for support.
