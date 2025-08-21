from oss4climate.src.parsers.opensustain_tech import (
    fetch_all_project_urls_from_opensustain_webpage,
    fetch_categorised_projects_from_opensustain_webpage,
)
from oss4climate.src.scraper import ParsingTargets, scrape_all_targets

categorised = fetch_categorised_projects_from_opensustain_webpage()
all_projs = fetch_all_project_urls_from_opensustain_webpage()


tgs = ParsingTargets(
    # github_repositories=all_projs.github_repositories[:5],
    # gitlab_projects=all_projs.gitlab_projects[:5],
    codeberg_repositories=all_projs.codeberg_repositories[:2],
    bitbucket_repositories=all_projs.bitbucket_repositories[:2],
)

res = scrape_all_targets(tgs)


print("OK")
