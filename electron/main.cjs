const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;
const BACKEND_PORT = 8765;

async function startPythonBackend() {
  if (await checkBackendHealth(1, 100)) {
    console.log('[Main] Reusing the existing Python backend.');
    return;
  }
  const isWindows = process.platform === 'win32';
  const projectRoot = path.join(__dirname, '..');
  const venvPython = isWindows 
    ? path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(projectRoot, '.venv', 'bin', 'python');
  const uvPath = path.join(process.env.USERPROFILE || '', '.local', 'bin', isWindows ? 'uv.exe' : 'uv');
  const serverScript = path.join(projectRoot, 'engine', 'server.py');

  const fs = require('fs');
  const executable = fs.existsSync(venvPython) ? venvPython : uvPath;
  const args = fs.existsSync(venvPython) ? [serverScript] : ['run', '--python', '3.11', serverScript];

  if (!fs.existsSync(executable)) {
    console.error(`[Main] Python backend runtime not found: ${executable}`);
    return false;
  }

  console.log(`[Main] Starting local Python ML backend using: ${executable}`);

  try {
    pythonProcess = spawn(executable, args, {
      cwd: projectRoot,
      env: { ...process.env, PYTHONUNBUFFERED: '1', PORT: String(BACKEND_PORT) },
      shell: false,
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log(`[Python Engine] ${data.toString().trim()}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python Engine Error] ${data.toString().trim()}`);
    });

    pythonProcess.on('close', (code) => {
      console.log(`[Python Engine] Process exited with code ${code}`);
    });
    return await checkBackendHealth();
  } catch (err) {
    console.error('[Main] Failed to spawn python backend via uv:', err);
    return false;
  }
}

function checkBackendHealth(retries = 30, interval = 500) {
  return new Promise((resolve) => {
    let attempts = 0;
    const check = () => {
      attempts++;
      const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/api/health`, (res) => {
        if (res.statusCode === 200) {
          console.log('[Main] Python backend healthcheck passed!');
          resolve(true);
        } else {
          retry();
        }
      });
      req.on('error', () => retry());
      req.end();
    };

    const retry = () => {
      if (attempts < retries) {
        setTimeout(check, interval);
      } else {
        console.warn('[Main] Python backend healthcheck timeout, proceeding anyway.');
        resolve(false);
      }
    };

    check();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: '#0a0d14',
    title: 'DietCode',
    frame: false,
    titleBarStyle: 'hidden',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
    },
  });

  const devUrl = 'http://localhost:5173';
  const isDev = process.env.NODE_ENV !== 'production';

  if (isDev) {
    mainWindow.loadURL(devUrl);
    // Open DevTools in dev mode
    // mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Window controls IPC
ipcMain.on('window-minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('window-maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.on('window-close', () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.handle('ping', () => 'pong');
ipcMain.handle('open-path', async (_event, targetPath) => {
  if (targetPath) {
    return shell.openPath(targetPath);
  }
});
ipcMain.handle('get-backend-status', async () => {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/api/health`, (res) => {
      resolve({ online: res.statusCode === 200, port: BACKEND_PORT });
    });
    req.on('error', () => resolve({ online: false, port: BACKEND_PORT }));
    req.end();
  });
});

app.whenReady().then(async () => {
  await startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

function cleanupPython() {
  if (pythonProcess) {
    console.log('[Main] Terminating Python process...');
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', pythonProcess.pid, '/f', '/t']);
      } else {
        pythonProcess.kill('SIGINT');
      }
    } catch (e) {
      console.error('[Main] Error killing python process:', e);
    }
    pythonProcess = null;
  }
}

app.on('before-quit', cleanupPython);
app.on('will-quit', cleanupPython);

app.on('window-all-closed', () => {
  cleanupPython();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
