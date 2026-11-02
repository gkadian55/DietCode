const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  ping: () => ipcRenderer.invoke('ping'),
  openPath: (targetPath) => ipcRenderer.invoke('open-path', targetPath),
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  maximizeWindow: () => ipcRenderer.send('window-maximize'),
  closeWindow: () => ipcRenderer.send('window-close'),
  isDesktop: true
});
