import React, { useEffect } from 'react';
import { Header } from './components/header/Header';
import { CriticalPathBanner } from './components/dashboard/CriticalPathBanner';
import { ExecutionSettingsPanel } from './components/dashboard/ExecutionSettingsPanel';
import { TokenomicsDashboard } from './components/dashboard/TokenomicsDashboard';
import { AgentCanvas } from './components/canvas/AgentCanvas';
import { NodeInspector } from './components/inspector/NodeInspector';
import { AddNodeModal } from './components/modal/AddNodeModal';
import { ExportModal } from './components/modal/ExportModal';
import { useDagStore } from './store/useDagStore';

export function App() {
  const { checkHealth, decomposeGoal, refreshProviders, goalInput } = useDagStore();

  useEffect(() => {
    // Initial health check and graph initialization
    const init = async () => {
      await checkHealth();
      await refreshProviders();
      await decomposeGoal(goalInput);
    };
    init();

    // Periodic healthcheck
    const interval = setInterval(() => {
      checkHealth();
      refreshProviders();
    }, 4000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-container">
      <Header />
      <div className="workspace-layout">
        <div className="canvas-area">
          <CriticalPathBanner />
          <ExecutionSettingsPanel />
          <AgentCanvas />
          <TokenomicsDashboard />
        </div>
        <NodeInspector />
      </div>
      <AddNodeModal />
      <ExportModal />
    </div>
  );
}

export default App;
