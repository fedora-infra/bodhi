#!/usr/bin/env python3

import os
import time
import sys
from argparse import ArgumentParser


DEFAULT_TIMEOUT = 120


class TimeoutError(Exception):
    pass


def wait_for_file(path: str, dir_not_empty: bool, timeout: int):
    """Check that a file exists.

    Args:
        path: The file path in the container.
        timeout: How long to wait before throwing an exception.
    """
    while timeout > 0:
        if os.path.exists(path):
            if not dir_not_empty or (os.path.isdir(path) and len(os.listdir(path)) > 0):
                break
        time.sleep(1)
        timeout = timeout - 1
    if timeout == 0:
        raise TimeoutError


def main():
    parser = ArgumentParser()
    parser.add_argument("path", help="the file or directory to wait for")
    parser.add_argument(
        "-d",
        "--dir-not-empty",
        action="store_true",
        help="wait for a file to be present in the directory",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="wait this many seconds",
    )
    args = parser.parse_args()

    try:
        wait_for_file(args.path, args.dir_not_empty, args.timeout)
    except TimeoutError:
        print(f"Timeout reached waiting for {args.path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
