const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { setTimeout: pause } = require("node:timers/promises");
const vscode = require("vscode");

const dashboardUrl = "http://127.0.0.1:8766/";

function isDashboard(execution) {
  const task = execution.task;
  const root = task.scope?.uri?.fsPath;
  return (
    vscode.workspace.isTrusted &&
    root &&
    vscode.workspace.workspaceFolders?.some(
      (folder) => folder.uri.fsPath === root,
    ) &&
    task.name === "dashboard" &&
    task.execution instanceof vscode.ProcessExecution &&
    path.basename(task.execution.process) === "make" &&
    task.execution.args.length === 1 &&
    task.execution.args[0] === "run" &&
    fs.existsSync(path.join(root, "project", "dev.py")) &&
    fs.existsSync(path.join(root, "project", "homelab_dashboard"))
  );
}

function isReady(signal) {
  return new Promise((resolve) => {
    const request = http.get(dashboardUrl, { signal }, (response) => {
      response.resume();
      resolve(response.statusCode === 200);
    });
    request.on("error", () => resolve(false));
    request.setTimeout(1000, () => request.destroy());
  });
}

function activate(context) {
  const pending = new Map();
  const output = vscode.window.createOutputChannel("Homelab Dashboard Preview");
  context.subscriptions.push(output);

  async function openWhenReady(execution) {
    if (!isDashboard(execution) || pending.has(execution)) return;
    const controller = new AbortController();
    pending.set(execution, controller);
    try {
      const deadline = Date.now() + 60000;
      while (!controller.signal.aborted && Date.now() < deadline) {
        if (await isReady(controller.signal)) {
          if (controller.signal.aborted) return;
          await vscode.commands.executeCommand(
            "workbench.action.browser.open",
            {
              url: dashboardUrl,
              reuseUrlFilter: "http://{127.0.0.1,localhost}:8766",
            },
          );
          output.appendLine(
            "Dashboard ready; opened or refreshed its browser tab.",
          );
          return;
        }
        await pause(250, undefined, { signal: controller.signal });
      }
      if (!controller.signal.aborted) {
        output.appendLine(
          "Dashboard did not become ready within 60 seconds; no browser tab opened.",
        );
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        output.appendLine(`Could not open dashboard preview: ${error.message}`);
        void vscode.window.showWarningMessage(
          "Dashboard preview could not open. See the Homelab Dashboard Preview output channel.",
        );
      }
    } finally {
      pending.delete(execution);
    }
  }

  function cancel(event) {
    pending.get(event.execution)?.abort();
  }

  context.subscriptions.push(
    vscode.tasks.onDidStartTaskProcess(
      (event) => void openWhenReady(event.execution),
    ),
    vscode.tasks.onDidEndTaskProcess(cancel),
    vscode.tasks.onDidEndTask(cancel),
    {
      dispose: () => {
        for (const controller of pending.values()) controller.abort();
      },
    },
  );
  for (const execution of vscode.tasks.taskExecutions)
    void openWhenReady(execution);
}

module.exports = { activate };
