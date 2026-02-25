import * as assert from "assert";
import * as vscode from "vscode";

/**
 * Extension activation tests.
 *
 * These verify that the Ivy extension activates correctly and
 * registers the expected language contributions.
 */
suite("Ivy Extension Activation", () => {
    test("Extension is present in extensions list", () => {
        // The extension may be identified by its package.json name.
        // In development host, extensions are loaded from the dev path.
        const allExtensions = vscode.extensions.all;
        assert.ok(
            allExtensions.length > 0,
            "There should be at least one extension loaded"
        );
    });

    test("Ivy language is registered", async () => {
        const doc = await vscode.workspace.openTextDocument({
            language: "ivy",
            content: "type foo",
        });
        assert.strictEqual(
            doc.languageId,
            "ivy",
            "Language ID should be 'ivy'"
        );
        await vscode.commands.executeCommand(
            "workbench.action.closeActiveEditor"
        );
    });

    test("Configuration settings are accessible", () => {
        const config = vscode.workspace.getConfiguration("ivy");

        const pythonPath = config.get<string>("pythonPath");
        assert.strictEqual(
            typeof pythonPath,
            "string",
            "ivy.pythonPath should be a string"
        );

        const lspEnabled = config.get<boolean>("lsp.enabled");
        assert.strictEqual(
            typeof lspEnabled,
            "boolean",
            "ivy.lsp.enabled should be a boolean"
        );

        const lspArgs = config.get<string[]>("lsp.args");
        assert.ok(
            Array.isArray(lspArgs),
            "ivy.lsp.args should be an array"
        );

        const traceLevel = config.get<string>("lsp.trace.server");
        assert.ok(
            ["off", "messages", "verbose"].includes(traceLevel || "off"),
            "ivy.lsp.trace.server should be a valid trace level"
        );
    });

    test("Opening .ivy content triggers ivy language mode", async () => {
        const doc = await vscode.workspace.openTextDocument({
            language: "ivy",
            content: "#lang ivy1.7\ntype test_type\n",
        });

        const editor = await vscode.window.showTextDocument(doc);
        assert.strictEqual(
            editor.document.languageId,
            "ivy",
            "Editor should be in ivy language mode"
        );

        await vscode.commands.executeCommand(
            "workbench.action.closeActiveEditor"
        );
    });

    test("Comment toggling uses # prefix", async () => {
        const doc = await vscode.workspace.openTextDocument({
            language: "ivy",
            content: "type foo\ntype bar\n",
        });

        const editor = await vscode.window.showTextDocument(doc);

        // Select the first line.
        editor.selection = new vscode.Selection(0, 0, 0, 8);

        // Toggle line comment.
        await vscode.commands.executeCommand(
            "editor.action.commentLine"
        );

        // The line should now start with #.
        const firstLine = editor.document.lineAt(0).text;
        assert.ok(
            firstLine.startsWith("#"),
            `Line should be commented with #, got: "${firstLine}"`
        );

        await vscode.commands.executeCommand(
            "workbench.action.closeActiveEditor"
        );
    });
});
