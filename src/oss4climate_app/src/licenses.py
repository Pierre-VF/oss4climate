"""
Module to manage licenses
"""

from enum import Enum

from oss4climate.src.log import log_warning


class LicenseCategoriesEnum(Enum):
    APACHE = "Apache"
    BSD = "BSD"
    CREATIVE_COMMON = "Creative Common"
    ECLIPSE = "Eclipse"
    GNU_AGPL = "GNU AGPL"
    GNU_GPL = "GNU GPL"
    GNU_LGPL = "GNU LGPL"
    MIT = "MIT"
    OTHER = "Other"
    UNKNOWN = "Unknown"


def license_category_from_license_name(name: str) -> LicenseCategoriesEnum:
    if name in ["Apache License 2.0"]:
        out = LicenseCategoriesEnum.APACHE
    elif name in [
        'BSD 2-Clause "Simplified" License',
        "BSD 3-Clause Clear License",
        'BSD 3-Clause "New" or "Revised" License',
    ]:
        out = LicenseCategoriesEnum.BSD
    elif name in [
        "Creative Commons Attribution 4.0 International",
        "Creative Commons Attribution Share Alike 4.0 International",
        "Creative Commons Attribution Non Commercial No Derivatives 4.0 International",
        "Creative Commons Zero v1.0 Universal",
    ]:
        out = LicenseCategoriesEnum.CREATIVE_COMMON
    elif name in ["Eclipse Public License 1.0", "Eclipse Public License 2.0"]:
        out = LicenseCategoriesEnum.ECLIPSE
    elif name in [
        "GNU Affero General Public License v3.0",
    ]:
        out = LicenseCategoriesEnum.GNU_AGPL
    elif name in [
        "GNU General Public License v2.0",
        "GNU General Public License v3.0",
        "GNU General Public License v3.0 only",
        "GNU General Public License v3.0 or later",
    ]:
        out = LicenseCategoriesEnum.GNU_GPL
    elif name in [
        "GNU Lesser General Public License v2.1",
        "GNU Lesser General Public License v2.1 only",
        "GNU Lesser General Public License v3.0",
    ]:
        out = LicenseCategoriesEnum.GNU_LGPL
    elif name in ["MIT License", "MIT No Attribution"]:
        out = LicenseCategoriesEnum.MIT
    elif name in [
        None,
        "Academic Free License v3.0",
        "Artistic License 2.0",
        "Boost Software License 1.0",
        "European Union Public License 1.1",
        "European Union Public License 1.2",
        "ISC License",
        "Mozilla Public License 2.0",
        "Other",
        "The Unlicense",
    ]:
        out = LicenseCategoriesEnum.OTHER
    else:
        log_warning(f"License not covered by enum classification ({name})")
        out = LicenseCategoriesEnum.UNKNOWN
    return out
