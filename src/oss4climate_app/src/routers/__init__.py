from functools import lru_cache

from oss4climate.src.config import FILE_INPUT_LISTINGS_INDEX
from oss4climate.src.parsers.licenses import (
    licence_url_from_license_name,
)
from oss4climate.src.parsers.listings import ResourceListing


@lru_cache(maxsize=2)
def listing_credits(html: bool = True) -> str:
    list_of_listings = ResourceListing.from_json(FILE_INPUT_LISTINGS_INDEX)

    def f_clean_name(x: str) -> str:
        out = x.replace("https://", "")
        if out.endswith("/"):
            out = out[:-1]
        for j in ["github.com/", "gitlab.com/"]:
            if out.startswith(j):
                out = out[len(j) :]
        return out

    df = list_of_listings.to_dataframe()
    # Sorting listings by descending number of datasets (and requiring at least 2 targets to be credited)
    min_targets = 2

    for i, r in df.iterrows():
        if (not isinstance(r["license_url"], str)) or r["license_url"] == "NaN":
            df.loc[i, "license_url"] = licence_url_from_license_name(r["license"])

    df_no_nas = (
        df.dropna()
        .sort_values("target_count", ascending=False)
        .query(f"target_count>={min_targets}")
    )

    if html:

        def _f_clean_text(i: dict) -> str:
            x = f'<b><a href="{i["url"]}">{f_clean_name(i["url"])}</a></b>'
            license = i.get("license")
            license_url = i.get("license_url")
            if license not in [None, "?", "Other"]:
                if license_url is None:
                    license_url = licence_url_from_license_name(license)
                if license_url:
                    x += f""" licensed under <i><a href="{license_url}">{license}</a></i>"""
                else:
                    x += f" licensed under {license}"
            x += f""" ({int(i["target_count"])} entries)"""
            return x

    else:

        def _f_clean_text(i: dict) -> str:
            x = f'{f_clean_name(i["url"])} ({i["url"]})'
            license = i.get("license")
            license_url = i.get("license_url")
            if license not in [None, "?", "Other"]:
                if license_url is None:
                    license_url = licence_url_from_license_name(license)
                if license_url:
                    x += f" licensed under {license} ({license_url})"
                else:
                    x += f" licensed under {license}"
            x += f""" ({int(i["target_count"])} entries)"""
            return x

    html_credit_text = ", ".join([_f_clean_text(i) for __, i in df_no_nas.iterrows()])
    return html_credit_text


if __name__ == "__main__":
    x = listing_credits()
