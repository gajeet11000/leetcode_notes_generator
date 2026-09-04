"""Main CLI entrypoint for leetnotes_core."""

from leetnotes_core.leetcode.client import LeetCodeAuthenticationError
from leetnotes_core.logging_config import configure_logging

from leetnotes_cli import cli

PROG_NAME = "leetnotes"


def main() -> None:
    configure_logging()
    try:
        cli(prog_name=PROG_NAME)
    except LeetCodeAuthenticationError as exc:
        raise SystemExit(f"Error: {exc}")


if __name__ == "__main__":
    main()
