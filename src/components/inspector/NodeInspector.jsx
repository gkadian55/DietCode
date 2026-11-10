import React, { useState, useEffect } from 'react';
import { useDagStore } from '../../store/useDagStore';
import { 
  X, 
  Trash2, 
  Plus, 
  CheckCircle2, 
  AlertTriangle, 
  Sliders, 
  Terminal, 
  Code2, 
  Copy, 
  Check, 
  Play, 
  Loader2, 
  Clock, 
  Cpu, 
  Sparkles,
  RotateCcw
} from 'lucide-react';

const IMAGE_PATTERN = /!\[([^\]]*)\]\((https?:\/\/[^)\s]+|data:image\/[^)\s]+)\)|(https?:\/\/[^\s"'<>]+\.(?:png|jpe?g|gif|webp|svg)(?:\?[^\s"'<>]*)?)/gi;

const renderOutput = (output) => {
  const parts = [];
  let cursor = 0;
  let match;
  IMAGE_PATTERN.lastIndex = 0;

  while ((match = IMAGE_PATTERN.exec(output)) !== null) {
    if (match.index > cursor) {
      parts.push(
        <pre className="output-text-block" key={`text-${cursor}`}>
          {output.slice(cursor, match.index)}
        </pre>
      );
    }

    const alt = match[1] || 'Generated image';
    const source = match[2] || match[3];
    parts.push(
      <figure className="output-image-block" key={`image-${match.index}`}>
        <img src={source} alt={alt} loading="lazy" />
        <figcaption>{alt}</figcaption>
      </figure>
    );
    cursor = match.index + match[0].length;
  }

  if (cursor < output.length) {
    parts.push(
      <pre className="output-text-block" key={`text-${cursor}`}>
        {output.slice(cursor)}
      </pre>
    );
  }

  return parts;
};

export const NodeInspector = () => {
  const { 
    selectedNode, 
    setSelectedNode, 
    updateNodeData, 
    removeNode, 
    setAddModalOpen,
    executeNode
  } = useDagStore();
  
  const [activeTab, setActiveTab] = useState('config'); // 'config' | 'output'
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [assignedAgent, setAssignedAgent] = useState('');
  const [copied, setCopied] = useState(false);
  const [isLocalExecuting, setIsLocalExecuting] = useState(false);

  useEffect(() => {
    if (selectedNode) {
      setTitle(selectedNode.data.title || '');
      setDescription(selectedNode.data.description || '');
      setAssignedAgent(selectedNode.data.assignedAgent || selectedNode.data.recommendedAgent?.id || 'gpt-4o');
      
      // Auto-switch to output tab if node just completed execution
      if (selectedNode.data.executionOutput && selectedNode.data.executionStatus === 'completed') {
        setActiveTab('output');
      }
      if (selectedNode.data.executionStatus === 'failed') {
        setActiveTab('output');
      }
    }
  }, [selectedNode]);

  if (!selectedNode) return null;

  const data = selectedNode.data;
  const evals = data.modelEvaluations || {};
  const executionStatus = data.executionStatus || 'pending';
  const hasOutput = Boolean(data.executionOutput);
  const isFailed = executionStatus === 'failed';
  const isRunning = executionStatus === 'running' || isLocalExecuting;

  const handleTitleBlur = () => {
    if (title !== data.title) {
      updateNodeData(selectedNode.id, { title });
    }
  };

  const handleDescriptionBlur = () => {
    if (description !== data.description) {
      updateNodeData(selectedNode.id, { description });
    }
  };

  const handleAgentSelect = (modelId) => {
    setAssignedAgent(modelId);
    updateNodeData(selectedNode.id, { assignedAgent: modelId });
  };

  const handleDelete = () => {
    removeNode(selectedNode.id);
  };

  const handleAddChild = () => {
    setAddModalOpen(true, selectedNode.id);
  };

  const handleCopyOutput = async () => {
    if (!data.executionOutput) return;
    try {
      await navigator.clipboard.writeText(data.executionOutput);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Clipboard copy failed:', err);
    }
  };

  const handleRunTask = async () => {
    setIsLocalExecuting(true);
    setActiveTab('output');
    try {
      await executeNode(selectedNode.id);
    } finally {
      setIsLocalExecuting(false);
    }
  };

  return (
    <aside className="inspector-drawer">
      {/* Header */}
      <div className="inspector-header">
        <div className="inspector-title">
          <Sliders size={16} color="#6366f1" />
          <span>Task Inspector</span>
        </div>
        <button 
          className="window-btn" 
          onClick={() => setSelectedNode(null)}
          title="Close Inspector"
        >
          <X size={15} />
        </button>
      </div>

      {/* Segmented Tab Navigation */}
      <div className="inspector-tabs-nav">
        <button 
          className={`inspector-tab-btn ${activeTab === 'config' ? 'active' : ''}`}
          onClick={() => setActiveTab('config')}
        >
          <Sliders size={13} />
          <span>Configuration</span>
        </button>
        <button 
          className={`inspector-tab-btn ${activeTab === 'output' ? 'active' : ''}`}
          onClick={() => setActiveTab('output')}
        >
          <Code2 size={13} />
          <span>Execution Output</span>
          {hasOutput && <span className="inspector-tab-dot completed" />}
          {isRunning && <span className="inspector-tab-dot running" />}
          {isFailed && <span className="inspector-tab-dot failed" />}
        </button>
      </div>

      {/* TAB 1: CONFIGURATION */}
      {activeTab === 'config' && (
        <div className="inspector-body">
          {/* Node ID & Category */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#64748b' }}>
              ID: {selectedNode.id}
            </span>
            <span className="agent-node-category">{data.category}</span>
          </div>

          {/* Title Field */}
          <div className="form-group">
            <label className="form-label">Task Name</label>
            <input 
              type="text" 
              className="form-input" 
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={handleTitleBlur}
              placeholder="Subtask title"
            />
          </div>

          {/* Description Field */}
          <div className="form-group">
            <label className="form-label">Prompt & Task Context</label>
            <textarea 
              className="form-textarea" 
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onBlur={handleDescriptionBlur}
              placeholder="Detailed agent prompt instructions"
            />
            <span style={{ fontSize: 10.5, color: '#64748b' }}>
              Editing prompt triggers real-time token forecast recalculation.
            </span>
          </div>

          {/* Forecasted Tokenomics */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 10,
            padding: 12
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 8 }}>
              Self-Trained Model Forecast
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, textAlign: 'center' }}>
              <div>
                <div style={{ fontSize: 10, color: '#64748b' }}>INPUT TOKENS</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700 }}>
                  {(data.predictedTokens?.input || 0).toLocaleString()}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: '#64748b' }}>OUTPUT TOKENS</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700 }}>
                  {(data.predictedTokens?.output || 0).toLocaleString()}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: '#64748b' }}>COMPLEXITY</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: '#6366f1' }}>
                  {data.complexityScore || 50}/100
                </div>
              </div>
            </div>
          </div>

          {/* Model Evaluation & Routing Matrix */}
          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label className="form-label">Multi-LLM Execution Matrix</label>
              <span style={{ fontSize: 10, color: '#06b6d4' }}>Click to override</span>
            </div>

            <div className="llm-cards-grid">
              {Object.values(evals).map((evalItem) => {
                const isSelected = assignedAgent === evalItem.id;
                const isRecommended = data.recommendedAgent?.id === evalItem.id;

                return (
                  <div 
                    key={evalItem.id} 
                    className={`llm-cost-card ${isSelected ? 'active' : ''}`}
                    onClick={() => handleAgentSelect(evalItem.id)}
                    style={{
                      borderLeft: `3px solid ${evalItem.color}`
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 12.5, fontWeight: 600, color: evalItem.color }}>
                          {evalItem.name}
                        </span>
                        {isRecommended && (
                          <span style={{ 
                            fontSize: 9, 
                            color: '#10b981', 
                            background: 'rgba(16, 185, 129, 0.15)', 
                            padding: '1px 5px', 
                            borderRadius: 3, 
                            fontWeight: 700 
                          }}>
                            AI PICK
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 10.5, color: '#64748b', marginTop: 2 }}>
                        Reasoning: {evalItem.reasoningScore}/100 • {evalItem.latencySec}s
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12.5, fontWeight: 700 }}>
                        ${evalItem.totalCost?.toFixed(4)}
                      </div>
                      {isSelected && (
                        <span style={{ fontSize: 9.5, color: '#6366f1', fontWeight: 600 }}>Active</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: 8, marginTop: 'auto', paddingTop: 16 }}>
            <button 
              className="btn btn-secondary" 
              style={{ flex: 1 }}
              onClick={handleAddChild}
            >
              <Plus size={14} />
              Subtask
            </button>
            <button 
              className="btn btn-primary" 
              style={{ flex: 1.2 }}
              onClick={handleRunTask}
              disabled={isRunning}
            >
              <Play size={14} />
              {isRunning ? 'Running...' : 'Execute Task'}
            </button>
            <button 
              className="btn btn-danger" 
              style={{ width: 42 }}
              onClick={handleDelete}
              title="Delete task"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      )}

      {/* TAB 2: EXECUTION OUTPUT & ERROR INSPECTOR */}
      {activeTab === 'output' && (
        <div className="inspector-body">
          {/* Status & Control Banner */}
          <div className={`execution-status-card status-${executionStatus}`}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {executionStatus === 'completed' && <CheckCircle2 size={16} color="#10b981" />}
                {isRunning && <Loader2 size={16} color="#06b6d4" className="spin-animation" />}
                {isFailed && <AlertTriangle size={16} color="#f43f5e" />}
                {executionStatus === 'pending' && <Clock size={16} color="#94a3b8" />}
                
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {executionStatus === 'completed' && 'Execution Completed'}
                    {isRunning && 'Executing Task...'}
                    {isFailed && 'Execution Failed'}
                    {executionStatus === 'pending' && 'Ready for Execution'}
                  </div>
                  <div style={{ fontSize: 10.5, color: '#94a3b8', marginTop: 1 }}>
                    Model: <span style={{ color: '#fff', fontFamily: 'var(--font-mono)' }}>
                      {data.executionModel || data.assignedAgent || data.recommendedAgent?.name || 'Auto-Routed'}
                    </span>
                    {data.executionMode && (
                      <span style={{ color: data.executionMode === 'simulated' ? '#fbbf24' : '#10b981', marginLeft: 8 }}>
                        {data.executionMode === 'simulated' ? 'SIMULATED' : 'LIVE'}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <button 
                className="btn btn-primary btn-sm"
                onClick={handleRunTask}
                disabled={isRunning}
                style={{ padding: '6px 12px', fontSize: 11 }}
              >
                {isRunning ? (
                  <>
                    <Loader2 size={12} className="spin-animation" />
                    Running
                  </>
                ) : hasOutput ? (
                  <>
                    <RotateCcw size={12} />
                    Re-Run
                  </>
                ) : (
                  <>
                    <Play size={12} />
                    Run Task
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Actual Token Metrics (When Completed) */}
          {data.actualTokens && (
            <div className="execution-metrics-bar">
              <div className="exec-metric-item">
                <span className="exec-metric-lbl">Actual Prompt In</span>
                <span className="exec-metric-num">
                  {(data.actualTokens.input || 0).toLocaleString()}
                </span>
                <span className="exec-metric-sub">
                  forecast: {(data.predictedTokens?.input || 0).toLocaleString()}
                </span>
              </div>
              <div className="exec-metric-item">
                <span className="exec-metric-lbl">Actual Output</span>
                <span className="exec-metric-num" style={{ color: '#10b981' }}>
                  {(data.actualTokens.output || 0).toLocaleString()}
                </span>
                <span className="exec-metric-sub">
                  forecast: {(data.predictedTokens?.output || 0).toLocaleString()}
                </span>
              </div>
              <div className="exec-metric-item">
                <span className="exec-metric-lbl">Total Actual</span>
                <span className="exec-metric-num" style={{ color: '#6366f1' }}>
                  {(data.actualTokens.total || 0).toLocaleString()}
                </span>
                <span className="exec-metric-sub">tokens processed</span>
              </div>
            </div>
          )}

          {/* Failure Alert Banner */}
          {isFailed && data.executionError && (
            <div className="execution-error-callout">
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#f43f5e', fontWeight: 600, fontSize: 12 }}>
                <AlertTriangle size={14} />
                <span>Execution Diagnostic Details</span>
              </div>
              <p style={{ fontSize: 11.5, color: '#fda4af', margin: '6px 0', fontFamily: 'var(--font-mono)', lineHeight: 1.5 }}>
                {data.executionError}
              </p>
              {data.executionErrorCategory && (
                <div style={{ color: '#fbbf24', fontSize: 11 }}>
                  Category: {data.executionErrorCategory.replaceAll('_', ' ')}
                </div>
              )}
              {data.executionFallbackReason && (
                <div style={{ color: '#cbd5e1', fontSize: 11, marginTop: 5 }}>
                  Fallback reason: {data.executionFallbackReason}
                </div>
              )}
              <div className="execution-error-tip">
                💡 <strong>Troubleshooting Tip:</strong> Make sure API keys are present in <code>.env</code> (e.g. <code>GEMINI_API_KEY</code>). For offline local execution, DietCode automatically uses simulation fallbacks or Ollama.
              </div>
            </div>
          )}

          {/* Generated Code / Output Box */}
          {hasOutput ? (
            <div className="execution-output-section">
              <div className="execution-output-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Terminal size={14} color="#6366f1" />
                  <span style={{ fontSize: 11.5, fontWeight: 600, color: '#f1f5f9' }}>
                    Generated Deliverable
                  </span>
                </div>
                <button 
                  className={`btn-copy ${copied ? 'copied' : ''}`}
                  onClick={handleCopyOutput}
                  title="Copy full deliverable code to clipboard"
                >
                  {copied ? (
                    <>
                      <Check size={12} color="#10b981" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy size={12} />
                      <span>Copy Output</span>
                    </>
                  )}
                </button>
              </div>

              <div className="code-viewer-wrapper">
                <div className="output-content">
                  {renderOutput(data.executionOutput)}
                </div>
              </div>
            </div>
          ) : !isRunning && !isFailed ? (
            /* Pending Empty State */
            <div className="execution-empty-state">
              <div className="empty-icon-circle">
                <Code2 size={24} color="#6366f1" />
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9', marginTop: 12 }}>
                Task Not Yet Executed
              </div>
              <p style={{ fontSize: 11.5, color: '#64748b', textAlign: 'center', maxWidth: 280, marginTop: 4, lineHeight: 1.5 }}>
                Click <strong>"Run Task"</strong> above or <strong>"Run DAG"</strong> in the top toolbar to execute this task with the assigned model and view generated code deliverables.
              </p>
            </div>
          ) : null}
        </div>
      )}
    </aside>
  );
};
