import React, { useEffect, useState } from 'react';
import { Settings, ChevronDown, ChevronUp } from 'lucide-react';
import { useDagStore } from '../../store/useDagStore';

export const ExecutionSettingsPanel = () => {
  const [open, setOpen] = useState(false);
  const { executionSettings, setExecutionSettings, isExecuting, providers, providersLoading, refreshProviders } = useDagStore();

  useEffect(() => {
    refreshProviders();
  }, [refreshProviders]);

  return (
    <div style={{ position: 'absolute', top: 78, right: 20, zIndex: 30, width: 270, background: 'rgba(13, 18, 31, 0.94)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, boxShadow: '0 8px 24px rgba(0,0,0,0.35)' }}>
      <button onClick={() => setOpen(!open)} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '9px 12px', color: '#cbd5e1', background: 'transparent', border: 0, cursor: 'pointer', fontSize: 12 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}><Settings size={14} color="#6366f1" /> Execution settings</span>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <div style={{ padding: '0 12px 12px', display: 'grid', gap: 9 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#94a3b8', fontSize: 10 }}>
            <span>Provider status</span>
            <button onClick={refreshProviders} disabled={providersLoading} style={{ color: '#93c5fd', background: 'none', border: 0, cursor: 'pointer', fontSize: 10 }}>
              {providersLoading ? 'Checking...' : 'Refresh'}
            </button>
          </div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {providers.map((provider) => (
              <span key={provider.id} title={provider.model || provider.id} style={{ padding: '3px 6px', borderRadius: 5, fontSize: 10, color: provider.available ? '#6ee7b7' : '#fda4af', background: provider.available ? 'rgba(16,185,129,0.12)' : 'rgba(244,63,94,0.12)' }}>
                {provider.id}: {provider.available ? 'online' : 'offline'}
              </span>
            ))}
          </div>
          <label className="form-label">Routing mode
            <select className="form-input" value={executionSettings.mode} onChange={(e) => setExecutionSettings({ mode: e.target.value })} disabled={isExecuting}>
              <option value="hybrid">Hybrid routing</option>
              <option value="selected">Primary model only</option>
              <option value="ollama_only">Ollama only</option>
            </select>
          </label>
          {executionSettings.mode !== 'ollama_only' && (
            <label className="form-label">Primary model
              <select className="form-input" value={executionSettings.primary_model} onChange={(e) => setExecutionSettings({ primary_model: e.target.value })} disabled={isExecuting}>
                <option value="gemini-3-5-flash-lite">Gemini 3.5 Flash Lite</option>
                <option value="gemini-3-8-flash">Gemini 3.8 Flash</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="claude-3-5-sonnet">Claude Sonnet</option>
              </select>
            </label>
          )}
          <label className="form-label">Request timeout (seconds)
            <input className="form-input" type="number" min="5" max="300" step="5" value={executionSettings.request_timeout} onChange={(e) => setExecutionSettings({ request_timeout: Math.min(300, Math.max(5, Number(e.target.value) || 30)) })} disabled={isExecuting} />
          </label>
          <label className="form-label">Retries
            <select className="form-input" value={executionSettings.max_retries} onChange={(e) => setExecutionSettings({ max_retries: Number(e.target.value) })} disabled={isExecuting}>
              <option value="0">0</option><option value="1">1</option><option value="2">2</option><option value="3">3</option>
            </select>
          </label>
          <label className="form-label">Parent context limit
            <input className="form-input" type="number" min="1000" max="50000" step="1000" value={executionSettings.max_context_chars} onChange={(e) => setExecutionSettings({ max_context_chars: Math.min(50000, Math.max(1000, Number(e.target.value) || 12000)) })} disabled={isExecuting} />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 7, color: '#cbd5e1', fontSize: 11 }}>
            <input type="checkbox" checked={executionSettings.allow_fallback} onChange={(e) => setExecutionSettings({ allow_fallback: e.target.checked })} disabled={isExecuting} />
            Use simulation fallback if provider fails
          </label>
        </div>
      )}
    </div>
  );
};
