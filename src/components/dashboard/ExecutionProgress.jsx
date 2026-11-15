import React from 'react';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { useDagStore } from '../../store/useDagStore';

export const ExecutionProgress = () => {
  const { isExecuting, executionProgress } = useDagStore();
  const { completed, total } = executionProgress;

  if (!isExecuting && total === 0) return null;

  const progressPercent = total > 0 ? Math.round((completed / total) * 100) : 0;
  const label = isExecuting
    ? `${completed}/${total} tasks completed`
    : `${completed}/${total} tasks completed`;

  return (
    <div className={`execution-progress ${isExecuting ? 'is-running' : 'is-finished'}`}>
      {isExecuting ? <Loader2 size={13} className="spin-animation" /> : <CheckCircle2 size={13} />}
      <span>{label}</span>
      <div className="execution-progress-track" aria-label={`${progressPercent}% complete`}>
        <div className="execution-progress-fill" style={{ width: `${progressPercent}%` }} />
      </div>
    </div>
  );
};
