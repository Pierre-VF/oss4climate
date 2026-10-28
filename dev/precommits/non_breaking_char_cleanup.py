#!/usr/bin/env python3
import os
import sys


def replace_nbsp(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = content.replace("\u00a0", " ")
    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    return False


if __name__ == "__main__":
    files = sys.argv[1:]
    for filepath in files:
        if os.path.isfile(filepath) and replace_nbsp(filepath):
            print(f"Replaced non-breaking spaces in: {filepath}")
