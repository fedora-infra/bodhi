#!/usr/bin/env python3

"""
This script browses through git commit history (starting at latest tag), collects all authors of
commits and creates fragment for `towncrier`_ tool.

It's meant to be run during the release process, before generating the release notes.

Example::

    $ python get_authors.py

.. _towncrier: https://github.com/hawkowl/towncrier/

Authors:
    Aurelien Bompard
    Michal Konecny
"""

import os
from argparse import ArgumentParser
from subprocess import check_output


EXCLUDE = []

last_tag = check_output(
    "git tag | sort -n | tail -n 1", shell=True, universal_newlines=True
).strip()

args_parser = ArgumentParser()
args_parser.add_argument(
    "until",
    nargs="?",
    default="HEAD",
    help="Consider all commits until this one (default: %(default)s).",
)
args_parser.add_argument(
    "since",
    nargs="?",
    default=last_tag,
    help="Consider all commits since this one (default: %(default)s).",
)
args = args_parser.parse_args()

authors = {}
log_range = args.since + ".." + args.until
output = check_output(
    ["git", "log", log_range, "--format=%ae\t%an"], universal_newlines=True
)
for line in output.splitlines():
    email, fullname = line.split("\t")
    email = email.split("@")[0].replace(".", "")
    if email in authors:
        continue
    authors[email] = fullname

for nick, fullname in authors.items():
    if fullname in EXCLUDE or fullname.endswith("[bot]"):
        continue
    filename = f"{nick}.author"
    if os.path.exists(filename):
        continue
    print(f"Adding author {fullname} ({nick})")
    with open(filename, "w") as f:
        f.write(fullname)
        f.write("\n")
