"""Ivy Language Server implementation."""

import logging
import os

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
        self._indexer = None
        self._parser = None

        from ivy_lsp.features import (
            definition,
            document_symbols,
            references,
            workspace_symbols,
        )

        document_symbols.register(self)
        workspace_symbols.register(self)
        definition.register(self)
        references.register(self)

    def initialized(self, params):
        """Handle the initialized notification."""
        logger.info("Ivy Language Server initialized")
        self._setup_indexer()

    def _setup_indexer(self):
        """Create and populate the workspace indexer."""
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        ws_folders = self.workspace.folders
        if ws_folders:
            root = list(ws_folders.values())[0].uri.replace("file://", "")
        else:
            root = os.getcwd()

        self._parser = IvyParserWrapper()
        resolver = IncludeResolver(root)
        self._indexer = WorkspaceIndexer(root, self._parser, resolver)
        try:
            self._indexer.index_workspace()
            logger.info("Workspace indexing complete")
        except Exception:
            logger.exception("Workspace indexing failed")
