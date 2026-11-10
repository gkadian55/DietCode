import React, { useState } from 'react';
import { useDagStore } from '../../store/useDagStore';
import { BarChart3, ChevronDown, ChevronUp, ShieldCheck, Zap } from 'lucide-react';

export const TokenomicsDashboard = () => {
  const [isExpanded, setIsExpanded] = useState(false);
  const { aggregates } = useDagStore();
  const { comparison, agentDistribution, nodeCount, tokenSavings } = aggregates;

  return (
    <div style={{
      position: 'absolute',
      bottom: 14,
      left: 20,
      width: 480,
      background: 'rgba(13, 18, 31, 0.85)',
      backdropFilter: 'blur(16px)',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      borderRadius: 14,
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
      zIndex: 25,
      overflow: 'hidden',
      transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
    }}>
      {/* Header Toggle */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          cursor: 'pointer',
          background: 'rgba(255, 255, 255, 0.02)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600 }}>
          <BarChart3 size={15} color="#6366f1" />
          <span>Multi-LLM Cost Matrix & Tokenomics</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#94a3b8', fontSize: 11 }}>
          <span>{nodeCount} Tasks Benchmarked</span>
          {isExpanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div style={{ padding: '12px 16px 16px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Comparison Cards */}
          {tokenSavings && (
            <div style={{ padding: '9px 10px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: 8, border: '1px solid rgba(16, 185, 129, 0.25)' }}>
              <div style={{ fontSize: 10, color: '#6ee7b7', textTransform: 'uppercase' }}>Actual token savings</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                <span>{tokenSavings.actualTotal.toLocaleString()} actual / {tokenSavings.forecastTotal.toLocaleString()} forecast</span>
                <strong style={{ color: tokenSavings.savedTokens >= 0 ? '#10b981' : '#f97316' }}>
                  {tokenSavings.savedTokens >= 0 ? `${tokenSavings.savedTokens.toLocaleString()} saved` : `${Math.abs(tokenSavings.savedTokens).toLocaleString()} over`}
                </strong>
              </div>
              <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 3 }}>{tokenSavings.savingsPercent}% difference from forecast</div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            <div style={{ padding: '8px 10px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: 8, border: '1px solid rgba(255, 255, 255, 0.06)' }}>
              <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase' }}>All-GPT-4o Total</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: '#10b981' }}>
                ${(comparison?.allGpt4oCost || 0).toFixed(4)}
              </div>
            </div>

            <div style={{ padding: '8px 10px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: 8, border: '1px solid rgba(255, 255, 255, 0.06)' }}>
              <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase' }}>All-Claude 3.5 Sonnet</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: '#f97316' }}>
                ${(comparison?.allClaudeCost || 0).toFixed(4)}
              </div>
            </div>

            <div style={{ padding: '8px 10px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: 8, border: '1px solid rgba(255, 255, 255, 0.06)' }}>
              <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase' }}>All-Gemini 2.0 Flash</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: '#6366f1' }}>
                ${(comparison?.allGeminiCost || 0).toFixed(4)}
              </div>
            </div>

            <div style={{ 
              padding: '8px 10px', 
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(16, 185, 129, 0.15))', 
              borderRadius: 8, 
              border: '1px solid rgba(99, 102, 241, 0.3)' 
            }}>
              <div style={{ fontSize: 10, color: '#93c5fd', textTransform: 'uppercase', fontWeight: 600 }}>
                DietCode Pareto Routing
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 700, color: '#fff' }}>
                ${(comparison?.dietCodeOptimizedCost || 0).toFixed(4)}
              </div>
            </div>
          </div>

          {/* Model Distribution Pills */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 10.5, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Allocated Agent Breakdown:
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {Object.entries(agentDistribution || {}).map(([agentId, count]) => (
                <div 
                  key={agentId}
                  style={{
                    fontSize: 11,
                    fontFamily: 'var(--font-mono)',
                    padding: '3px 8px',
                    borderRadius: 6,
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6
                  }}
                >
                  <span style={{ fontWeight: 600 }}>{agentId}</span>
                  <span style={{ color: '#06b6d4', fontWeight: 700 }}>×{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
