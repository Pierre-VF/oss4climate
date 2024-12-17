"""
Parser for Git repositories
"""

import os
from typing import Any, Callable

from oss4climate.src.log import log_info


def clone_git_repository(url: str, path: str) -> None:
    """Clones a Git repository in a given folder

    Note: this is a simple implementation assuming that Git is installed and configured on your system

    :param url: URL of the git (for git clone command)
    :param path: path of the directory in which the Git must be cloned
    """
    os.system(f"git clone {url} {path}")
    log_info(f"Cloned git in {path}")


def map_function_on_all_files_in_folder(
    f: Callable,
    path: str,
    apply_on_file_content: bool = True,
    include_subfolders: bool = True,
) -> dict[str, Any]:
    """
    Maps the results of calling a function on all the files of a given directory

    :param f: function to map
    :param path: path of the directory
    _param apply_on_file_content: if True, applies the function on the content (read in text mode) of the file,
        else applies the function on the file path
    :param include_subfolders: if True, maps the function to all files in sub-directories too, defaults to True
    :return: dictionary of results of calling the function f on all files
    """
    out = dict()
    for i in os.scandir(path):
        if i.name in [".git", ".github", ".devcontainer"]:
            # Ignore typically irrelevant folders
            pass
        else:
            path_i = i.path
            if i.is_file():
                if apply_on_file_content:
                    with open(path_i, "r") as f_i:
                        out[path_i] = f(f_i.read())
                else:
                    out[path_i] = f(path_i)
            elif i.is_dir():
                if include_subfolders:
                    out_sub = map_function_on_all_files_in_folder(
                        f,
                        path=path_i,
                        apply_on_file_content=apply_on_file_content,
                        include_subfolders=True,
                    )
                    out = out | out_sub
    return out
