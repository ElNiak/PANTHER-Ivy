import * as cp from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

let cachedPythonPath: string | undefined;

/**
 * Discover a Python interpreter suitable for running the Ivy LSP server.
 *
 * Search order:
 *   1. `ivy.pythonPath` setting (if non-empty)
 *   2. Workspace `.venv/bin/python` (or `.venv/Scripts/python.exe` on Windows)
 *   3. `python3` on PATH
 *   4. `python` on PATH
 *
 * The result is cached for the session — call `clearCache()` to reset.
 */
export async function findPython(): Promise<string | undefined> {
    if (cachedPythonPath) {
        return cachedPythonPath;
    }

    const configured = vscode.workspace
        .getConfiguration("ivy")
        .get<string>("pythonPath", "");

    if (configured) {
        if (await isPythonValid(configured)) {
            cachedPythonPath = configured;
            return cachedPythonPath;
        }
        vscode.window.showWarningMessage(
            `Configured ivy.pythonPath "${configured}" is not a valid Python interpreter.`
        );
    }

    // Check workspace virtual environment
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (workspaceFolders) {
        for (const folder of workspaceFolders) {
            const venvPython = getVenvPython(folder.uri.fsPath);
            if (venvPython && (await isPythonValid(venvPython))) {
                cachedPythonPath = venvPython;
                return cachedPythonPath;
            }
        }
    }

    // Try system python3 then python
    for (const candidate of ["python3", "python"]) {
        if (await isPythonValid(candidate)) {
            cachedPythonPath = candidate;
            return cachedPythonPath;
        }
    }

    return undefined;
}

/**
 * Check whether `ivy_lsp` is importable from the given Python interpreter.
 * Returns the version string on success, `undefined` on failure.
 */
export async function checkIvyLsp(
    pythonPath: string
): Promise<string | undefined> {
    return new Promise((resolve) => {
        cp.execFile(
            pythonPath,
            ["-c", "import ivy_lsp; print(ivy_lsp.__version__)"],
            { timeout: 10_000 },
            (error, stdout) => {
                if (error) {
                    resolve(undefined);
                } else {
                    resolve(stdout.trim() || undefined);
                }
            }
        );
    });
}

/** Clear the cached Python path (e.g. after a config change). */
export function clearCache(): void {
    cachedPythonPath = undefined;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function getVenvPython(workspaceRoot: string): string | undefined {
    const isWindows = process.platform === "win32";
    const venvBin = isWindows
        ? path.join(workspaceRoot, ".venv", "Scripts", "python.exe")
        : path.join(workspaceRoot, ".venv", "bin", "python");

    return fs.existsSync(venvBin) ? venvBin : undefined;
}

function isPythonValid(pythonPath: string): Promise<boolean> {
    return new Promise((resolve) => {
        cp.execFile(
            pythonPath,
            ["--version"],
            { timeout: 5_000 },
            (error) => {
                resolve(!error);
            }
        );
    });
}
