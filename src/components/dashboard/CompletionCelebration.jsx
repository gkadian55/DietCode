import React from 'react';
import { useDagStore } from '../../store/useDagStore';

const COMPLETION_GIF_URL = '/assets/task-complete.gif';

export const CompletionCelebration = () => {
  const visible = useDagStore((state) => state.showCompletionCelebration);
  if (!visible) return null;

  return (
    <div className="completion-celebration" role="status" aria-live="polite">
      <div className="completion-celebration-card">
        <img
          className="completion-celebration-gif"
          src={COMPLETION_GIF_URL}
          alt="Celebration"
        />
        <strong>All tasks completed!</strong>
      </div>
    </div>
  );
};
