"""Entry point for running the Ivy Language Server over stdio."""

import logging
import sys


def main():
    """Start the Ivy Language Server over stdio."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    from ivy_lsp.server import IvyLanguageServer

    server = IvyLanguageServer()
    server.start_io()


if __name__ == "__main__":
    main()
