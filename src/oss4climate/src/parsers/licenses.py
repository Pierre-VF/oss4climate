"""
Module to manage licenses
"""

from oss4climate.src.log import log_warning
from oss4climate.src.models import EnumLicenseCategories

# Using https://opensource.org/license/ to determine canonical URLs
_url_by_license = {
    "Apache License 2.0": "https://www.apache.org/licenses/LICENSE-2.0.txt",
    'BSD 2-Clause "Simplified" License': "https://opensource.org/license/bsd-2-clause",  # Not ideal
    "BSD 3-Clause Clear License": "https://opensource.org/license/bsd-3-clause",  # Not ideal
    'BSD 3-Clause "New" or "Revised" License': "https://opensource.org/license/bsd-3-clause",  # Not ideal
    "Creative Commons Attribution 4.0 International": "https://creativecommons.org/licenses/by/4.0/",
    "Creative Commons Attribution Share Alike 4.0 International": "https://creativecommons.org/licenses/by-sa/4.0/",
    "Creative Commons Attribution Non Commercial No Derivatives 4.0 International": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
    "Creative Commons Zero v1.0 Universal": "https://creativecommons.org/publicdomain/zero/1.0/",
    "Eclipse Public License 1.0": "https://www.eclipse.org/org/documents/epl-1.0/EPL-1.0.txt",
    "Eclipse Public License 2.0": "https://www.eclipse.org/legal/epl-2.0/",
    "GNU Affero General Public License v3.0": "https://www.gnu.org/licenses/agpl-3.0.txt",
    "GNU General Public License v2.0": "https://www.gnu.org/licenses/gpl-2.0.txt",
    "GNU General Public License v3.0": "https://www.gnu.org/licenses/gpl-3.0.txt",
    "GNU General Public License v3.0 only": "https://www.gnu.org/licenses/gpl-3.0.txt",
    "GNU General Public License v3.0 or later": "https://www.gnu.org/licenses/gpl-3.0.txt",  # Not ideal
    "GNU Lesser General Public License v2.1": "https://www.gnu.org/licenses/lgpl-2.1.txt",
    "GNU Lesser General Public License v2.1 only": "https://www.gnu.org/licenses/lgpl-2.1.txt",
    "GNU Lesser General Public License v3.0": "https://www.gnu.org/licenses/lgpl-3.0.txt",
    "MIT License": "https://opensource.org/license/mit",  # Not ideal
    "MIT No Attribution": "https://opensource.org/license/mit-0",  # Not ideal
    "Academic Free License v3.0": "https://opensource.org/license/afl-3-0-php",  # Not ideal
    "Artistic License 2.0": "https://www.perlfoundation.org/artistic-license-20.html",
    "Boost Software License 1.0": "https://www.boost.org/LICENSE_1_0.txt",
    "European Union Public License 1.1": "https://interoperable-europe.ec.europa.eu/licence/european-union-public-licence-version-11-eupl",
    "European Union Public License 1.2": "https://interoperable-europe.ec.europa.eu/licence/european-union-public-licence-version-12-eupl",
    "ISC License": "https://opensource.org/license/isc-license-txt",  # Not ideal
    "Mozilla Public License 2.0": "https://www.mozilla.org/en-US/MPL/2.0/",
    "Other": None,
    "The Unlicense": "https://unlicense.org/",
}


def licence_url_from_license_name(name: str) -> str | None:
    return _url_by_license.get(name)


def license_category_from_license_name(name: str) -> EnumLicenseCategories:
    if not isinstance(name, str):
        out = EnumLicenseCategories.UNKNOWN
    elif name in ["Apache License 2.0"]:
        out = EnumLicenseCategories.APACHE
    elif name in [
        'BSD 2-Clause "Simplified" License',
        "BSD 3-Clause Clear License",
        'BSD 3-Clause "New" or "Revised" License',
    ]:
        out = EnumLicenseCategories.BSD
    elif name in [
        "Creative Commons Attribution 4.0 International",
        "Creative Commons Attribution Share Alike 4.0 International",
        "Creative Commons Attribution Non Commercial No Derivatives 4.0 International",
        "Creative Commons Zero v1.0 Universal",
    ]:
        out = EnumLicenseCategories.CREATIVE_COMMON
    elif name in ["Eclipse Public License 1.0", "Eclipse Public License 2.0"]:
        out = EnumLicenseCategories.ECLIPSE
    elif name in [
        "GNU Affero General Public License v3.0",
    ]:
        out = EnumLicenseCategories.GNU_AGPL
    elif name in [
        "GNU General Public License v2.0",
        "GNU General Public License v3.0",
        "GNU General Public License v3.0 only",
        "GNU General Public License v3.0 or later",
    ]:
        out = EnumLicenseCategories.GNU_GPL
    elif name in [
        "GNU Lesser General Public License v2.1",
        "GNU Lesser General Public License v2.1 only",
        "GNU Lesser General Public License v3.0",
    ]:
        out = EnumLicenseCategories.GNU_LGPL
    elif name in ["MIT License", "MIT No Attribution"]:
        out = EnumLicenseCategories.MIT
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
        out = EnumLicenseCategories.OTHER
    else:
        log_warning(f"License not covered by enum classification ({name})")
        out = EnumLicenseCategories.UNKNOWN
    return out
