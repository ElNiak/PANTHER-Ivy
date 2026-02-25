"""Ivy Language Server implementation."""

import logging

import lsprotocol.types as lsp
from pygls.lsp.server import LanguageServer

from ivy_lsp import __version__

logger = logging.getLogger(__name__)


class IvyLanguageServer(LanguageServer):
    """Language server for Ivy formal specification files."""

    def __init__(self):
        super().__init__(
            name="ivy-language-server",
            version=__version__,
        )

        @self.feature(lsp.INITIALIZED)
        def _on_initialized(params: lsp.InitializedParams) -> None:
            logger.info("Ivy Language Server initialized")
