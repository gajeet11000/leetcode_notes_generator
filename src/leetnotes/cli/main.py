"""Main CLI entrypoint for leetnotes."""

from leetnotes.cli import cli
from leetnotes.leetcode.client import LeetCodeAuthenticationError
from leetnotes.logging_config import configure_logging

PROG_NAME = "leetnotes"


def main() -> None:
    configure_logging()
    try:
        cli(prog_name=PROG_NAME)
    except LeetCodeAuthenticationError as exc:
        raise SystemExit(f"Error: {exc}")


if __name__ == "__main__":
    main()
