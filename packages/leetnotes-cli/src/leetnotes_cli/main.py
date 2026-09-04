"""Main CLI entrypoint for leetnotes_core."""

from leetnotes_core.leetcode.client import LeetCodeAuthenticationError

from leetnotes_cli import cli
from leetnotes_cli.logging import configure_logging

PROG_NAME = "leetnotes"


def main() -> None:
    configure_logging()
    try:
        cli(prog_name=PROG_NAME)
    except LeetCodeAuthenticationError as exc:
        raise SystemExit(f"Error: {exc}")


if __name__ == "__main__":
    main()
