import * as vscode from "vscode";
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    Trace,
    TransportKind,
} from "vscode-languageclient/node";
import { findPython, checkIvyLsp, clearCache } from "./pythonFinder";

let client: LanguageClient | undefined;
let statusBarItem: vscode.StatusBarItem;

export async function activate(
    context: vscode.ExtensionContext
): Promise<void> {
    statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    context.subscriptions.push(statusBarItem);

    const config = vscode.workspace.getConfiguration("ivy");
    const lspEnabled = config.get<boolean>("lsp.enabled", true);

    if (!lspEnabled) {
        setStatus("syntax-only");
        return;
    }

    await startClient(context);

    // Restart the server when relevant settings change.
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration(async (e) => {
            if (
                e.affectsConfiguration("ivy.pythonPath") ||
                e.affectsConfiguration("ivy.lsp.enabled") ||
                e.affectsConfiguration("ivy.lsp.args")
            ) {
                clearCache();
                await stopClient();

                const nowEnabled = vscode.workspace
                    .getConfiguration("ivy")
                    .get<boolean>("lsp.enabled", true);

                if (nowEnabled) {
                    await startClient(context);
                } else {
                    setStatus("syntax-only");
                }
            }
        })
    );
}

export async function deactivate(): Promise<void> {
    await stopClient();
}

// ---------------------------------------------------------------------------
// Client lifecycle
// ---------------------------------------------------------------------------

async function startClient(
    context: vscode.ExtensionContext
): Promise<void> {
    const pythonPath = await findPython();

    if (!pythonPath) {
        vscode.window.showWarningMessage(
            "Ivy LSP: No Python interpreter found. " +
                "Syntax highlighting is still active. " +
                'Set "ivy.pythonPath" to enable full language support.'
        );
        setStatus("syntax-only");
        return;
    }

    const ivyLspVersion = await checkIvyLsp(pythonPath);

    if (!ivyLspVersion) {
        vscode.window.showErrorMessage(
            "Ivy LSP: The ivy_lsp package is not installed. " +
                "Install it with: pip install -e '.[lsp]' " +
                "(from the panther_ivy directory).",
            "Copy Install Command"
        ).then((selection) => {
            if (selection === "Copy Install Command") {
                vscode.env.clipboard.writeText('pip install -e ".[lsp]"');
            }
        });
        setStatus("syntax-only");
        return;
    }

    const extraArgs = vscode.workspace
        .getConfiguration("ivy")
        .get<string[]>("lsp.args", []);

    const serverOptions: ServerOptions = {
        command: pythonPath,
        args: ["-m", "ivy_lsp", ...extraArgs],
        transport: TransportKind.stdio,
    };

    const traceLevel = vscode.workspace
        .getConfiguration("ivy")
        .get<string>("lsp.trace.server", "off");

    const clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: "file", language: "ivy" }],
        outputChannelName: "Ivy Language Server",
        traceOutputChannel: vscode.window.createOutputChannel(
            "Ivy LSP Trace"
        ),
    };

    client = new LanguageClient(
        "ivy-language-server",
        "Ivy Language Server",
        serverOptions,
        clientOptions
    );

    // Set trace level if not "off".
    if (traceLevel !== "off") {
        const trace =
            traceLevel === "verbose" ? Trace.Verbose : Trace.Messages;
        await client.setTrace(trace);
    }

    try {
        await client.start();
        setStatus("running", ivyLspVersion);
    } catch (err) {
        const message =
            err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(
            `Ivy LSP: Failed to start server — ${message}`
        );
        setStatus("error");
    }
}

async function stopClient(): Promise<void> {
    if (client) {
        try {
            await client.stop();
        } catch {
            // Client may already be stopped.
        }
        client = undefined;
    }
}

// ---------------------------------------------------------------------------
// Status bar
// ---------------------------------------------------------------------------

type StatusKind = "running" | "syntax-only" | "error";

function setStatus(kind: StatusKind, version?: string): void {
    switch (kind) {
        case "running":
            statusBarItem.text = `$(check) Ivy LSP${version ? ` v${version}` : ""}`;
            statusBarItem.tooltip = "Ivy Language Server is running";
            statusBarItem.backgroundColor = undefined;
            break;
        case "syntax-only":
            statusBarItem.text = "$(warning) Ivy: Syntax Only";
            statusBarItem.tooltip =
                "Ivy LSP is not running — syntax highlighting only";
            statusBarItem.backgroundColor = new vscode.ThemeColor(
                "statusBarItem.warningBackground"
            );
            break;
        case "error":
            statusBarItem.text = "$(error) Ivy LSP: Error";
            statusBarItem.tooltip = "Ivy Language Server encountered an error";
            statusBarItem.backgroundColor = new vscode.ThemeColor(
                "statusBarItem.errorBackground"
            );
            break;
    }
    statusBarItem.show();
}
