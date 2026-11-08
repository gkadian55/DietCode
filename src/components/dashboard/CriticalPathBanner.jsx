import React from 'react';
import { useDagStore } from '../../store/useDagStore';
import { Layers, Clock, TrendingDown, Plus, Sparkles, Play, Download } from 'lucide-react';

export const CriticalPathBanner = () => {
  const { 
    aggregates, 
    setAddModalOpen, 
    replanGraph, 
    executeGraph, 
    exportProject, 
    exportLoading, 
    isLoading, 
    isExecuting, 
    executionError,
    executionSettings,
    setExecutionSettings
  } = useDagStore();
  const { 
    nodeCount, 
    totalInputTokens, 
    totalOutputTokens, 
    totalTokens, 
    criticalPath, 
    criticalPathLatencySec, 
    comparison 
  } = aggregates;

  return (
    <div className="floating-metrics-bar">
      <div className="metric-group">
        <div className="metric-item">
          <span className="metric-label">DAG Topology</span>
          <span className="metric-value" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Layers size={14} color="#6366f1" />
            {nodeCount} Nodes
          </span>
        </div>

        <div className="metric-item">
          <span className="metric-label">Forecasted Tokens</span>
          <span className="metric-value highlight-indigo">
            {(totalTokens || 0).toLocaleString()} <span style={{ fontSize: 11, fontWeight: 400, color: '#94a3b8' }}>
              ({((totalInputTokens || 0) / 1000).toFixed(1)}k In / {((totalOutputTokens || 0) / 1000).toFixed(1)}k Out)
            </span>
          </span>
        </div>

        <div className="metric-item">
          <span className="metric-label">Critical Path Latency</span>
          <span className="metric-value highlight-amber" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Clock size={14} color="#f97316" />
            {criticalPathLatencySec || 0}s
            <span style={{ fontSize: 10, color: '#94a3b8' }}>
              ({criticalPath?.length || 0} serial steps)
            </span>
          </span>
        </div>

        <div className="metric-item">
          <span className="metric-label">Optimized Cost</span>
          <span className="metric-value highlight-green" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            ${(comparison?.dietCodeOptimizedCost || 0).toFixed(4)}
            {comparison?.savingsPercentVsBaseline > 0 && (
              <span style={{ 
                fontSize: 10.5, 
                color: '#10b981', 
                background: 'rgba(16, 185, 129, 0.15)', 
                padding: '1px 5px', 
                borderRadius: 4, 
                display: 'inline-flex', 
                alignItems: 'center', 
                gap: 2 
              }}>
                <TrendingDown size={11} />
                {comparison.savingsPercentVsBaseline}% saved
              </span>
            )}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <select
          value={executionSettings.mode}
          onChange={(event) => setExecutionSettings({ mode: event.target.value })}
          disabled={isExecuting}
          title="Choose how tasks are routed"
          style={{
            height: 30,
            padding: '0 8px',
            color: '#cbd5e1',
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 6,
            fontSize: 11
          }}
        >
          <option value="hybrid">Hybrid routing</option>
          <option value="selected">Primary model only</option>
          <option value="ollama_only">Ollama only</option>
        </select>
        {executionSettings.mode !== 'ollama_only' && (
          <select
            value={executionSettings.primary_model}
            onChange={(event) => setExecutionSettings({ primary_model: event.target.value })}
            disabled={isExecuting}
            title="Select the primary cloud model"
            style={{
              height: 30,
              maxWidth: 130,
              padding: '0 8px',
              color: '#cbd5e1',
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 6,
              fontSize: 11
            }}
          >
            <option value="gemini-3-8-flash">Gemini 3.8 Flash</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="claude-3-5-sonnet">Claude Sonnet</option>
          </select>
        )}
        <button
          className="btn btn-primary btn-sm"
          onClick={executeGraph}
          title="Execute the DAG using the assigned models"
          disabled={isLoading || isExecuting || nodeCount === 0}
        >
          <Play size={13} />
          {isExecuting ? 'Executing...' : 'Run DAG'}
        </button>
        <button 
          className="btn btn-secondary btn-sm" 
          onClick={() => replanGraph()}
          title="Recalculate entire graph tokenomics"
          disabled={isLoading}
        >
          <Sparkles size={13} color="#6366f1" />
          Re-Benchmark
        </button>

        <button 
          className="btn btn-secondary btn-sm"
          onClick={exportProject}
          title="Export project codebase, architecture specs, and ZIP archive"
          disabled={isLoading || isExecuting || nodeCount === 0 || exportLoading}
        >
          <Download size={13} color="#10b981" />
          {exportLoading ? 'Exporting...' : 'Export Code'}
        </button>

        <button 
          className="btn btn-primary btn-sm"
          onClick={() => setAddModalOpen(true, null)}
        >
          <Plus size={13} />
          Add Custom Node
        </button>
      </div>
      {executionError && (
        <div style={{ color: '#f87171', fontSize: 11, marginTop: 6 }}>
          Execution error: {executionError}
        </div>
      )}
    </div>
  );
};
