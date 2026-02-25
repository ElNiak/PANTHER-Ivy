"""Tests for Task 1.1: Project Scaffolding."""

import importlib


class TestPackageImportable:
    """Verify ivy_lsp package structure."""

    def test_ivy_lsp_importable(self):
        import ivy_lsp

        assert ivy_lsp is not None

    def test_version_exists(self):
        import ivy_lsp

        assert hasattr(ivy_lsp, "__version__")
        assert isinstance(ivy_lsp.__version__, str)
        assert ivy_lsp.__version__ == "0.1.0"

    def test_parsing_subpackage_importable(self):
        import ivy_lsp.parsing

        assert ivy_lsp.parsing is not None

    def test_indexer_subpackage_importable(self):
        import ivy_lsp.indexer

        assert ivy_lsp.indexer is not None

    def test_features_subpackage_importable(self):
        import ivy_lsp.features

        assert ivy_lsp.features is not None

    def test_utils_subpackage_importable(self):
        import ivy_lsp.utils

        assert ivy_lsp.utils is not None


class TestIvyLanguageServer:
    """Verify IvyLanguageServer class."""

    def test_server_importable(self):
        from ivy_lsp.server import IvyLanguageServer

        assert IvyLanguageServer is not None

    def test_server_is_language_server_subclass(self):
        from pygls.lsp.server import LanguageServer

        from ivy_lsp.server import IvyLanguageServer

        assert issubclass(IvyLanguageServer, LanguageServer)

    def test_server_instantiation(self):
        from ivy_lsp.server import IvyLanguageServer

        server = IvyLanguageServer()
        assert server.name == "ivy-language-server"

    def test_server_version_matches_package(self):
        import ivy_lsp
        from ivy_lsp.server import IvyLanguageServer

        server = IvyLanguageServer()
        assert server.version == ivy_lsp.__version__


class TestEntryPoint:
    """Verify __main__ entry point."""

    def test_main_module_importable(self):
        import ivy_lsp.__main__

        assert ivy_lsp.__main__ is not None

    def test_main_function_callable(self):
        from ivy_lsp.__main__ import main

        assert callable(main)
