import React, { useState } from 'react';
import { useDagStore } from '../../store/useDagStore';
import { X, Plus, Sparkles } from 'lucide-react';

export const AddNodeModal = () => {
  const { isAddModalOpen, newSubtaskParentId, setAddModalOpen, addCustomNode, nodes } = useDagStore();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('Core Engineering');

  if (!isAddModalOpen) return null;

  const parentNode = newSubtaskParentId 
    ? nodes.find(n => n.id === newSubtaskParentId) 
    : null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    addCustomNode(
      {
        title: title.trim(),
        description: description.trim() || 'Custom agent subtask specification.',
        category
      },
      newSubtaskParentId
    );

    setTitle('');
    setDescription('');
  };

  return (
    <div className="modal-overlay" onClick={() => setAddModalOpen(false)}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            {parentNode ? `Add Dependent Subtask to "${parentNode.data.title}"` : 'Add New Task to DAG'}
          </div>
          <button 
            className="window-btn" 
            onClick={() => setAddModalOpen(false)}
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="form-group">
            <label className="form-label">Task Name</label>
            <input 
              type="text" 
              className="form-input" 
              placeholder="e.g., Implement Distributed Raft Consensus" 
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              autoFocus
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Category</label>
            <select 
              className="form-select"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="Architecture">Architecture</option>
              <option value="Core Engineering">Core Engineering</option>
              <option value="Backend">Backend Service</option>
              <option value="Frontend">Frontend Canvas / UI</option>
              <option value="Machine Learning">Machine Learning</option>
              <option value="Integration">Integration & IPC</option>
              <option value="QA & Testing">QA & Testing</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Prompt & Task Context</label>
            <textarea 
              className="form-textarea" 
              placeholder="Describe the instructions for the agent..." 
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div style={{ fontSize: 11, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Sparkles size={13} color="#6366f1" />
            <span>Local model will predict tokenomics and assign optimal agent on creation.</span>
          </div>

          <div className="modal-footer">
            <button 
              type="button" 
              className="btn btn-secondary" 
              onClick={() => setAddModalOpen(false)}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="btn btn-primary"
            >
              <Plus size={14} />
              Insert Node
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
