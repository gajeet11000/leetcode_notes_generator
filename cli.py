"""Backward-compatible CLI entrypoint. Delegates to `leetnotes.cli.main`."""

from leetnotes.cli.main import main

if __name__ == "__main__":
    main()
