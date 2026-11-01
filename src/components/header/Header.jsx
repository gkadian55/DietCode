import React, { useState, useEffect } from 'react';
import { useDagStore } from '../../store/useDagStore';
import { 
  GitFork, 
  Search, 
  Sparkles, 
  Minimize2, 
  Square, 
  X, 
  Loader2 
} from 'lucide-react';

const PRESET_GOALS = [
  { label: '⚡ Hello World', value: "Create a webpage with 'Hello World' only" },
  { label: '🌦️ Weather App', value: 'Build a real-time weather forecasting dashboard' },
  { label: '💬 Realtime Chat', value: 'Build a real-time chat application with WebSocket' },
  { label: '🏦 FinTech System', value: 'Distributed high-frequency fintech payment microservice with Kafka' }
];

export const Header = () => {
  const { 
    goalInput, 
    setGoalInput, 
    decomposeGoal, 
    isLoading, 
    backendStatus 
  } = useDagStore();

  const [inputVal, setInputVal] = useState(goalInput);

  // Synchronize local input state whenever goalInput updates
  useEffect(() => {
    setInputVal(goalInput);
  }, [goalInput]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    const target = inputVal.trim();
    if (!target) return;
    setGoalInput(target);
    decomposeGoal(target);
  };

  const handleSelectPreset = (presetVal) => {
    setInputVal(presetVal);
    setGoalInput(presetVal);
    decomposeGoal(presetVal);
  };

  const handleMinimize = () => {
    if (window.electronAPI) window.electronAPI.minimizeWindow();
  };

  const handleMaximize = () => {
    if (window.electronAPI) window.electronAPI.maximizeWindow();
  };

  const handleClose = () => {
    if (window.electronAPI) window.electronAPI.closeWindow();
  };

  return (
    <header className="header-bar">
      {/* Left: Brand Identity & Backend Status */}
      <div className="header-left">
        <div className="logo-badge">
          <div className="logo-icon">
            <GitFork size={17} />
          </div>
          <span>DietCode</span>
        </div>

        <div className="status-pill" title={backendStatus === 'online' ? 'Python ML backend is connected' : 'Running in client fallback mode'}>
          <div className={`status-dot ${backendStatus === 'online' ? 'online' : ''}`} />
          <span style={{ color: backendStatus === 'online' ? '#10b981' : '#94a3b8' }}>
            {backendStatus === 'online' ? 'Local ML Engine Online' : 'Engine Connecting / Fallback Mode'}
          </span>
        </div>
      </div>

      {/* Center: Interactive Project Goal Input & Presets */}
      <div className="header-center">
        <form onSubmit={handleSubmit} className="goal-input-box">
          <Search size={14} color="#64748b" />
          <input 
            type="text" 
            className="goal-input"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Describe what you want to build or work on..."
          />
          <button 
            type="submit" 
            className="btn btn-primary btn-sm"
            disabled={isLoading || !inputVal.trim()}
          >
            {isLoading ? (
              <>
                <Loader2 size={12} className="spin-animation" />
                <span>Decomposing...</span>
              </>
            ) : (
              <>
                <Sparkles size={12} />
                <span>Generate DAG</span>
              </>
            )}
          </button>
        </form>

        {/* Quick Demo Preset Chips */}
        <div className="preset-chips-container">
          {PRESET_GOALS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className="preset-chip-btn"
              onClick={() => handleSelectPreset(preset.value)}
              disabled={isLoading}
              title={`Switch query to: ${preset.value}`}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* Right: Window Controls */}
      <div className="header-right">
        <div className="window-controls">
          <button className="window-btn" onClick={handleMinimize} title="Minimize">
            <Minimize2 size={13} />
          </button>
          <button className="window-btn" onClick={handleMaximize} title="Maximize">
            <Square size={12} />
          </button>
          <button className="window-btn close" onClick={handleClose} title="Close">
            <X size={14} />
          </button>
        </div>
      </div>
    </header>
  );
};
