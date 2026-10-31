import React, { useState, useEffect } from 'react';
import { useDagStore } from '../../store/useDagStore';
import { X, Cpu, Zap, Trash2, Plus, CheckCircle2, AlertTriangle, Sliders } from 'lucide-react';

export const NodeInspector = () => {
  const { selectedNode, setSelectedNode, updateNodeData, removeNode, setAddModalOpen } = useDagStore();
  
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [assignedAgent, setAssignedAgent] = useState('');

  useEffect(() => {
    if (selectedNode) {
      setTitle(selectedNode.data.title || '');
      setDescription(selectedNode.data.description || '');
      setAssignedAgent(selectedNode.data.assignedAgent || selectedNode.data.recommendedAgent?.id || 'gpt-4o');
    }
  }, [selectedNode]);

  if (!selectedNode) return null;

  const data = selectedNode.data;
  const evals = data.modelEvaluations || {};

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

  return (
    <aside className="inspector-drawer">
      {/* Header */}
      <div className="inspector-header">
        <div className="inspector-title">
          <Sliders size={16} color="#6366f1" />
          <span>Task Inspector & Steering</span>
        </div>
        <button 
          className="window-btn" 
          onClick={() => setSelectedNode(null)}
          title="Close Inspector"
        >
          <X size={15} />
        </button>
      </div>

      {/* Body */}
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
            className="btn btn-danger" 
            style={{ flex: 1 }}
            onClick={handleDelete}
          >
            <Trash2 size={14} />
            Delete
          </button>
        </div>
      </div>
    </aside>
  );
};
