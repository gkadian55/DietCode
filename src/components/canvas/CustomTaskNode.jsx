import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { useDagStore } from '../../store/useDagStore';
import { Plus, Trash2 } from 'lucide-react';

export const CustomTaskNode = memo(({ id, data, selected }) => {
  const { aggregates, setSelectedNode, setAddModalOpen, removeNode } = useDagStore();
  const isCriticalPath = aggregates.criticalPath?.includes(id);

  const assignedAgentId = data.assignedAgent || data.recommendedAgent?.id;
  const currentModelEval = data.modelEvaluations?.[assignedAgentId] || {};
  const agentColor = data.recommendedAgent?.color || '#6366f1';
  const executionStatus = data.executionStatus || 'pending';
  const actualTokens = data.actualTokens;
  const statusColor = {
    queued: '#f59e0b',
    running: '#06b6d4',
    completed: '#10b981',
    failed: '#f43f5e'
  }[executionStatus] || '#94a3b8';

  const handleClick = (e) => {
    e.stopPropagation();
    setSelectedNode({ id, data });
  };

  const handleAddChild = (e) => {
    e.stopPropagation();
    setAddModalOpen(true, id);
  };

  const handleDelete = (e) => {
    e.stopPropagation();
    removeNode(id);
  };

  return (
    <div 
      className={`agent-node-card ${selected ? 'selected' : ''} ${isCriticalPath ? 'critical-path' : ''}`}
      onClick={handleClick}
    >
      {/* React Flow Handles */}
      <Handle 
        type="target" 
        position={Position.Left} 
        style={{ background: '#6366f1', width: 8, height: 8 }} 
      />

      {/* Top Category & Action Controls */}
      <div className="agent-node-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="agent-node-category">{data.category || 'Subtask'}</span>
          <span style={{ color: statusColor, fontSize: 9, fontWeight: 700, textTransform: 'uppercase' }}>
            {executionStatus}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {isCriticalPath && (
            <span style={{ fontSize: 9, color: '#f43f5e', fontWeight: 700, padding: '2px 4px', background: 'rgba(244,63,94,0.15)', borderRadius: 3 }}>
              CRITICAL
            </span>
          )}
          <button 
            className="window-btn" 
            title="Add dependent subtask" 
            onClick={handleAddChild}
            style={{ width: 22, height: 22 }}
          >
            <Plus size={12} />
          </button>
          <button 
            className="window-btn" 
            title="Delete node" 
            onClick={handleDelete}
            style={{ width: 22, height: 22, color: '#f43f5e' }}
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      {/* Task Title & Description */}
      <div className="agent-node-title">{data.title}</div>
      <div className="agent-node-desc">{data.description}</div>

      {/* Recommended/Assigned Agent Badge */}
      <div className="agent-allocation-badge" style={{ borderLeft: `3px solid ${agentColor}` }}>
        <div className="agent-badge-info">
          <div className="agent-avatar-dot" style={{ background: agentColor }} />
          <div>
            <div className="agent-badge-name" style={{ color: agentColor }}>
              {currentModelEval.name || data.recommendedAgent?.name || 'Agent'}
            </div>
            <div style={{ fontSize: 9.5, color: '#94a3b8' }}>
              {data.assignedAgent && data.assignedAgent !== data.recommendedAgent?.id 
                ? 'Human Override' 
                : 'Optimal Pareto Match'}
            </div>
          </div>
        </div>
        <div className="agent-badge-cost">
          ${(currentModelEval.totalCost || data.recommendedAgent?.estimatedCost || 0).toFixed(4)}
        </div>
      </div>

      {/* Token Metrics Row */}
      <div className="token-metrics-row">
        <div className="token-metric-cell">
          <div className="token-metric-label">{actualTokens ? 'Actual In' : 'Forecast In'}</div>
          <div className="token-metric-val">
            {(actualTokens?.input ?? data.predictedTokens?.input ?? 0).toLocaleString()}
          </div>
        </div>
        <div className="token-metric-cell">
          <div className="token-metric-label">{actualTokens ? 'Actual Out' : 'Forecast Out'}</div>
          <div className="token-metric-val">
            {(actualTokens?.output ?? data.predictedTokens?.output ?? 0).toLocaleString()}
          </div>
        </div>
        <div className="token-metric-cell">
          <div className="token-metric-label">Latency</div>
          <div className="token-metric-val" style={{ color: '#06b6d4' }}>
            {currentModelEval.latencySec || data.recommendedAgent?.estimatedLatency || 0}s
          </div>
          {executionStatus === 'failed' && data.executionError && (
            <div style={{ color: '#f87171', fontSize: 10, marginTop: 6 }}>
              {data.executionError}
            </div>
          )}
        </div>
      </div>

      <Handle 
        type="source" 
        position={Position.Right} 
        style={{ background: '#10b981', width: 8, height: 8 }} 
      />
    </div>
  );
});

CustomTaskNode.displayName = 'CustomTaskNode';
