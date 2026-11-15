import os
from ftplib import FTP

from oss4x.scripts.src.config import (
    FILE_OUTPUT_SUMMARY_TOML,
)
from oss4x.src.config import (
    SETTINGS,
)
from oss4x.src.log import log_info


def publish_to_ftp() -> None:
    """Exports data generated to FTP (requires .env to be defined with credentials to the FTP)

    :raises EnvironmentError: when the FTP credentials are not given in environment
    """
    # This should only be needed when publishing to FTP (as it's a side feature)
    from oss4x.app.src.config import (
        FILE_INPUT_LISTINGS_INDEX,
        FILE_OUTPUT_LISTING_FEATHER,
    )

    for v, i in [
        ("EXPORT_FTP_URL", SETTINGS.EXPORT_FTP_URL),
        ("EXPORT_FTP_USER", SETTINGS.EXPORT_FTP_USER),
        ("EXPORT_FTP_PASSWORD", SETTINGS.EXPORT_FTP_PASSWORD),
    ]:
        if i is None:
            raise OSError(f"{v} must be defined for FTP export to work")
        if len(i) == 0:
            raise OSError(f"{v} must have an adequate value for FTP export to work")
    files_out = [
        FILE_OUTPUT_SUMMARY_TOML,
        FILE_OUTPUT_LISTING_FEATHER,
        FILE_INPUT_LISTINGS_INDEX,
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
