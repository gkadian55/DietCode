import React, { useState } from 'react';
import { useDagStore } from '../../store/useDagStore';
import { 
  GitFork, 
  Search, 
  Sparkles, 
  Minimize2, 
  Square, 
  X, 
  Radio, 
  Activity 
} from 'lucide-react';

export const Header = () => {
  const { 
    goalInput, 
    setGoalInput, 
    decomposeGoal, 
    isLoading, 
    backendStatus 
  } = useDagStore();

  const [inputVal, setInputVal] = useState(goalInput);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    setGoalInput(inputVal);
    decomposeGoal(inputVal);
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
      {/* Left: Brand Identity */}
      <div className="header-left">
        <div className="logo-badge">
          <div className="logo-icon">
            <GitFork size={17} />
          </div>
          <span>DietCode</span>
        </div>

        {/* Backend Status Indicator */}
        <div className="status-pill">
          <div className={`status-dot ${backendStatus === 'online' ? 'online' : ''}`} />
          <span style={{ color: backendStatus === 'online' ? '#10b981' : '#94a3b8' }}>
            {backendStatus === 'online' ? 'Local ML Engine Online' : 'Engine Connecting...'}
          </span>
        </div>
      </div>

      {/* Center: Interactive Project Goal Input */}
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
            <Sparkles size={12} />
            {isLoading ? 'Decomposing...' : 'Generate DAG'}
          </button>
        </form>
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
