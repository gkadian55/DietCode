import React, { useEffect } from 'react';
import { useAuth } from '@clerk/react';
import { Header } from './components/header/Header';
import { DemoModeBanner } from './components/auth/DemoModeBanner';
import { CriticalPathBanner } from './components/dashboard/CriticalPathBanner';
import { ExecutionSettingsPanel } from './components/dashboard/ExecutionSettingsPanel';
import { TokenomicsDashboard } from './components/dashboard/TokenomicsDashboard';
import { CompletionCelebration } from './components/dashboard/CompletionCelebration';
import { AgentCanvas } from './components/canvas/AgentCanvas';
import { NodeInspector } from './components/inspector/NodeInspector';
import { AddNodeModal } from './components/modal/AddNodeModal';
import { ExportModal } from './components/modal/ExportModal';
import { OllamaFailureModal } from './components/modal/OllamaFailureModal';
import { useDagStore } from './store/useDagStore';
import { setAuthTokenGetter } from './utils/apiFetch';

export function App() {
  const { checkHealth, decomposeGoal, refreshProviders, goalInput } = useDagStore();
  const { getToken, isSignedIn } = useAuth();

  useEffect(() => {
    setAuthTokenGetter(getToken);
    useDagStore.getState().setAuthenticationState(Boolean(isSignedIn));
  }, [getToken, isSignedIn]);

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
      <DemoModeBanner />
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
      <OllamaFailureModal />
      <CompletionCelebration />
    </div>
  );
}

export default App;
