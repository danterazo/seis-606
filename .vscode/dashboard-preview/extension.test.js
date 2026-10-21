const assert = require("node:assert/strict");
const fs = require("node:fs");
const { EventEmitter } = require("node:events");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function fixture({
  statuses = [200],
  running = true,
  trusted = true,
  exists = true,
  commandFails = false,
} = {}) {
  const listeners = {};
  const commands = [];
  const messages = [];
  const logs = [];
  const responses = [...statuses];
  let requests = 0;
  let now = 0;
  class ProcessExecution {
    process = "make";
    args = ["run"];
  }
  const execution = {
    task: {
      name: "dashboard",
      scope: { uri: { fsPath: "/repo" } },
      execution: new ProcessExecution(),
    },
  };
  const api = {
    ProcessExecution,
    workspace: {
      isTrusted: trusted,
      workspaceFolders: [{ uri: { fsPath: "/repo" } }],
    },
    tasks: { taskExecutions: running ? [execution] : [] },
    commands: {
      async executeCommand(...args) {
        if (commandFails) throw new Error("unavailable");
        commands.push(args);
      },
    },
    window: {
      createOutputChannel: () => ({
        appendLine: (message) => logs.push(message),
        dispose() {},
      }),
      showWarningMessage: (message) => messages.push(message),
    },
  };
  for (const event of [
    "onDidStartTaskProcess",
    "onDidEndTaskProcess",
    "onDidEndTask",
  ]) {
    api.tasks[event] = (listener) => {
      listeners[event] = listener;
      return { dispose() {} };
    };
  }
  const mocks = {
    vscode: api,
    "node:path": path,
    "node:fs": { existsSync: () => exists },
    "node:timers/promises": {
      async setTimeout() {
        now += 250;
      },
    },
    "node:http": {
      get(url, options, callback) {
        assert.equal(url, "http://127.0.0.1:8766/");
        requests++;
        const request = new EventEmitter();
        request.setTimeout = () => request;
        request.destroy = () => request.emit("error", new Error("timeout"));
        queueMicrotask(() => {
          const status = responses.shift() ?? 503;
          if (options.signal.aborted || status === 0)
            request.emit("error", new Error("connection refused"));
          else callback({ statusCode: status, resume() {} });
        });
        return request;
      },
    },
  };
  const context = {
    module: { exports: {} },
    require: (name) => mocks[name],
    AbortController,
    Date: { now: () => now },
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, "extension.js"), "utf8"),
    context,
  );
  const subscriptions = [];
  context.module.exports.activate({ subscriptions });
  return {
    execution,
    listeners,
    commands,
    messages,
    logs,
    subscriptions,
    requests: () => requests,
  };
}

const settle = () => new Promise((resolve) => setImmediate(resolve));

test("loads an already-running dashboard and reuses its loopback browser tab", async () => {
  const state = fixture();
  await settle();
  assert.equal(state.commands.length, 1);
  assert.equal(state.commands[0][0], "workbench.action.browser.open");
  assert.equal(state.commands[0][1].url, "http://127.0.0.1:8766/");
  assert.equal(
    state.commands[0][1].reuseUrlFilter,
    "http://{127.0.0.1,localhost}:8766",
  );
});

test("waits through connection refusal and non-200 responses", async () => {
  const state = fixture({ statuses: [0, 503, 200] });
  await settle();
  assert.equal(state.requests(), 3);
  assert.equal(state.commands.length, 1);
});

test("handles later task starts and suppresses duplicate start events", async () => {
  const state = fixture({ running: false });
  state.listeners.onDidStartTaskProcess({ execution: state.execution });
  state.listeners.onDidStartTaskProcess({ execution: state.execution });
  await settle();
  assert.equal(state.commands.length, 1);
});

test("ignores untrusted workspaces, unrelated tasks, commands, and projects", async () => {
  for (const options of [{ trusted: false }, { exists: false }]) {
    const state = fixture(options);
    await settle();
    assert.equal(state.requests(), 0);
  }
  for (const mutate of [
    (task) => {
      task.name = "bash";
    },
    (task) => {
      task.execution.args = ["clean"];
    },
    (task) => {
      task.scope.uri.fsPath = "/other";
    },
  ]) {
    const state = fixture({ running: false });
    mutate(state.execution.task);
    state.listeners.onDidStartTaskProcess({ execution: state.execution });
    await settle();
    assert.equal(state.requests(), 0);
  }
});

test("cancels when the task ends or the extension is disposed", async () => {
  for (const event of ["onDidEndTask", "onDidEndTaskProcess", "dispose"]) {
    const state = fixture({ statuses: [0] });
    if (event === "dispose") state.subscriptions.at(-1).dispose();
    else state.listeners[event]({ execution: state.execution });
    await settle();
    assert.equal(state.commands.length, 0);
  }
});

test("times out without opening a failed server", async () => {
  const state = fixture({ statuses: [] });
  await settle();
  assert.equal(state.commands.length, 0);
  assert(state.logs.some((message) => message.includes("60 seconds")));
});

test("reports browser command failures without failing the task", async () => {
  const state = fixture({ commandFails: true });
  await settle();
  assert.equal(state.messages.length, 1);
});
