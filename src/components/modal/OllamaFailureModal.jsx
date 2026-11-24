import React from 'react';
import { AlertTriangle, Cloud, X } from 'lucide-react';
import { useDagStore } from '../../store/useDagStore';

export const OllamaFailureModal = () => {
  const {
    ollamaFailurePrompt,
    quitAfterOllamaFailure,
    continueAfterOllamaFailure
  } = useDagStore();

  if (!ollamaFailurePrompt) return null;

  const taskCount = ollamaFailurePrompt.taskIds?.length || 0;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-content" style={{ maxWidth: 440 }}>
        <div className="modal-header">
          <div className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertTriangle size={17} color="#fbbf24" />
            Ollama execution failed
          </div>
          <button className="window-btn" onClick={quitAfterOllamaFailure} title="Quit">
            <X size={16} />
          </button>
        </div>
        <div style={{ padding: '18px 20px', color: '#cbd5e1', lineHeight: 1.6 }}>
          <p style={{ margin: 0 }}>
            {ollamaFailurePrompt.message} {taskCount === 1 ? 'The task stopped.' : `${taskCount} tasks stopped.`}
          </p>
          <p style={{ margin: '10px 0 0', fontSize: 12, color: '#94a3b8' }}>
            Continue by switching the remaining execution to fully OpenRouter.
          </p>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={quitAfterOllamaFailure}>
            Quit
          </button>
          <button type="button" className="btn btn-primary" onClick={continueAfterOllamaFailure}>
            <Cloud size={14} />
            Continue with OpenRouter
          </button>
        </div>
      </div>
    </div>
  );
};
