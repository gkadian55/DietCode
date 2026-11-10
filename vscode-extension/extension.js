const vscode = require('vscode');

function backendUrl() {
  return vscode.workspace.getConfiguration('dietcode').get('backendUrl', 'http://127.0.0.1:8765');
}

async function postJson(path, payload) {
  const response = await fetch(`${backendUrl()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `DietCode returned HTTP ${response.status}`);
  }
  return data;
}

async function sendSelection() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage('Open a file before sending a selection to DietCode.');
    return;
  }

  const selection = editor.document.getText(editor.selection).trim();
  if (!selection) {
    vscode.window.showWarningMessage('Select code or text before sending it to DietCode.');
    return;
  }

  const prompt = await vscode.window.showInputBox({
    prompt: 'What should DietCode do with this selection?',
    value: 'Review and improve this code',
    ignoreFocusOut: true
  });
  if (!prompt) return;

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: 'DietCode is executing...' },
    async () => {
      try {
        const data = await postJson('/api/execute', {
          graph: {
            vscode_selection: {
              prompt: `${prompt}\n\nSelected content:\n${selection}`,
              model: 'gpt-4o',
              depends_on: []
            }
          },
          mode: 'hybrid',
          allow_fallback: true
        });
        const result = data.results?.vscode_selection;
        if (!result) throw new Error('DietCode returned no task result.');
        const channel = vscode.window.createOutputChannel('DietCode');
        channel.clear();
        channel.appendLine(`Execution: ${result.execution_mode || 'unknown'}`);
        channel.appendLine(`Model: ${result.routed_model || result.model || 'unknown'}`);
        channel.appendLine(`Tokens: ${result.total_tokens || 0}`);
        channel.appendLine('');
        channel.appendLine(result.text || result.error || 'No output returned.');
        channel.show(true);
      } catch (error) {
        vscode.window.showErrorMessage(`DietCode execution failed: ${error.message}`);
      }
    }
  );
}

function openDashboard() {
  vscode.env.openExternal(vscode.Uri.parse('http://127.0.0.1:5173'));
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand('dietcode.sendSelection', sendSelection),
    vscode.commands.registerCommand('dietcode.openDashboard', openDashboard)
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
