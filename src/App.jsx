import React, { useEffect, useRef } from 'react';
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
import { ProjectsModal } from './components/modal/ProjectsModal';
import { useDagStore } from './store/useDagStore';
import { setAuthTokenGetter } from './utils/apiFetch';

export function App() {
  const { checkHealth, refreshProviders, initializeLocalProjects } = useDagStore();
  const { getToken, isSignedIn } = useAuth();
  const projectInitializationStarted = useRef(false);

  useEffect(() => {
    setAuthTokenGetter(getToken);
    useDagStore.getState().setAuthenticationState(Boolean(isSignedIn));
  }, [getToken, isSignedIn]);

  useEffect(() => {
    // Initial health check and graph initialization
    if (!projectInitializationStarted.current) {
      projectInitializationStarted.current = true;
      const init = async () => {
        await checkHealth();
        await refreshProviders();
        await initializeLocalProjects();
      };
      init();
    }

    // Periodic healthcheck
    const interval = setInterval(() => {
      checkHealth();
      refreshProviders();
    }, 4000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    let saveTimer;
    const unsubscribe = useDagStore.subscribe((state, previousState) => {
      if (!state.currentProjectId) return;
      if (
        state.nodes === previousState.nodes
        && state.edges === previousState.edges
        && state.goalInput === previousState.goalInput
        && state.executionSettings === previousState.executionSettings
        && state.aggregates === previousState.aggregates
      ) return;
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => {
        useDagStore.getState().saveCurrentProject();
      }, 700);
    });

    const handlePageHide = () => {
      useDagStore.getState().saveCurrentProject();
    };
    window.addEventListener('pagehide', handlePageHide);

    return () => {
      clearTimeout(saveTimer);
      window.removeEventListener('pagehide', handlePageHide);
      unsubscribe();
    };
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
      <ProjectsModal />
      <CompletionCelebration />
    </div>
  );
}

export default App;
