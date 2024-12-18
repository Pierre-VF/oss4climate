import os
from ftplib import FTP

from oss4climate.scripts import (
    FILE_OUTPUT_LISTING_CSV,
    FILE_OUTPUT_LISTING_FEATHER,
    FILE_OUTPUT_OPTIMISED_LISTING_FEATHER,
    FILE_OUTPUT_SUMMARY_TOML,
)
from oss4climate.src.config import SETTINGS
from oss4climate.src.log import log_info


def publish_to_ftp() -> None:
    """Exports data generated to FTP (requires .env to be defined with credentials to the FTP)

    :raises EnvironmentError: when the FTP credentials are not given in environment
    """
    for i in [
        SETTINGS.EXPORT_FTP_URL,
        SETTINGS.EXPORT_FTP_USER,
        SETTINGS.EXPORT_FTP_PASSWORD,
    ]:
        if i is None:
            raise EnvironmentError(
                f"{i.__name__} must be defined for FTP export to work"
            )
        if len(i) == 0:
            raise EnvironmentError(
                f"{i.__name__} must have an adequate value for FTP export to work"
            )
    files_out = [
        FILE_OUTPUT_SUMMARY_TOML,
        FILE_OUTPUT_LISTING_CSV,
        FILE_OUTPUT_LISTING_FEATHER,
        FILE_OUTPUT_OPTIMISED_LISTING_FEATHER,
    ]

    with FTP(
        host=SETTINGS.EXPORT_FTP_URL,
        user=SETTINGS.EXPORT_FTP_USER,
        passwd=SETTINGS.EXPORT_FTP_PASSWORD,
    ) as ftp:
        try:
            ftp.mkd("oss4climate")
        except:
            pass
        ftp.cwd("oss4climate")
        for i in files_out:
            with open(i, "rb") as fp:
                log_info(f"Uploading {i}")
                ftp.storbinary("STOR %s" % os.path.basename(i), fp, blocksize=1024)
