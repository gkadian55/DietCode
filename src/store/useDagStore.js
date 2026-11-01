import { create } from 'zustand';
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react';

const API_BASE = 'http://127.0.0.1:8765';

// Convert React Flow's node/edge representation to the execution engine's
// dependency map. Edges are authoritative because users can edit them directly.
export const buildExecutionGraph = (nodes, edges) => {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const dependencies = new Map(nodes.map((node) => [node.id, []]));

  edges.forEach((edge) => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
      throw new Error(`Execution graph contains an unknown edge: ${edge.id || 'unnamed'}`);
    }
    dependencies.get(edge.target).push(edge.source);
  });

  return Object.fromEntries(nodes.map((node) => {
    const data = node.data || {};
    const model = data.assignedAgent || data.recommendedAgent?.id;
    if (!model) {
      throw new Error(`Task ${node.id} does not have an assigned model`);
    }

    const title = data.title || 'Untitled task';
    const description = data.description || '';
    return [
      node.id,
      {
        prompt: description ? `${title}\n\n${description}` : title,
        model,
        depends_on: dependencies.get(node.id)
      }
    ];
  }));
};

export const useDagStore = create((set, get) => ({
  nodes: [],
  edges: [],
  aggregates: {
    nodeCount: 0,
    edgeCount: 0,
    totalInputTokens: 0,
    totalOutputTokens: 0,
    totalTokens: 0,
    criticalPath: [],
    criticalPathLatencySec: 0,
    agentDistribution: {},
    comparison: {
      allGpt4oCost: 0,
      allClaudeCost: 0,
      allGeminiCost: 0,
      dietCodeOptimizedCost: 0,
      savingsPercentVsBaseline: 0
    }
  },
  selectedNode: null,
  goalInput: 'Multi-Agent Coding Assistant with Smart LLM Routing and Token Analytics',
  isLoading: false,
  isExecuting: false,
  executionError: null,
  backendStatus: 'checking',
  isAddModalOpen: false,
  newSubtaskParentId: null,

  setBackendStatus: (status) => set({ backendStatus: status }),
  setGoalInput: (goal) => set({ goalInput: goal }),
  setSelectedNode: (node) => set({ selectedNode: node }),
  setAddModalOpen: (open, parentId = null) => set({ isAddModalOpen: open, newSubtaskParentId: parentId }),
  getExecutionGraph: () => {
    const { nodes, edges } = get();
    return buildExecutionGraph(nodes, edges);
  },

  executeGraph: async () => {
    const { nodes, edges } = get();
    if (nodes.length === 0) return { results: {} };

    let graph;
    try {
      graph = buildExecutionGraph(nodes, edges);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Invalid execution graph';
      console.error('[Store] Failed to build execution graph:', err);
      set({ executionError: message });
      return null;
    }

    const queuedNodes = nodes.map((node) => ({
      ...node,
      data: { ...node.data, executionStatus: 'running', executionError: null }
    }));
    const curSelectedId = get().selectedNode?.id;

    set({
      isExecuting: true,
      executionError: null,
      nodes: queuedNodes,
      selectedNode: curSelectedId ? queuedNodes.find(n => n.id === curSelectedId) || get().selectedNode : get().selectedNode
    });

    try {
      const res = await fetch(`${API_BASE}/api/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ graph })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `HTTP error! status: ${res.status}`);
      }

      const results = data.results || {};
      const executedNodes = get().nodes.map((node) => {
        const result = results[node.id];
        if (!result) return node;
        return {
          ...node,
          data: {
            ...node.data,
            executionStatus: result.status,
            executionError: result.error,
            executionOutput: result.text,
            executionModel: result.routed_model || result.model,
            actualTokens: {
              input: result.prompt_tokens,
              output: result.completion_tokens,
              total: result.total_tokens
            }
          }
        };
      });

      const currentSelectedId = get().selectedNode?.id;
      const updatedSelectedNode = currentSelectedId ? executedNodes.find(n => n.id === currentSelectedId) : null;

      const totalActIn = executedNodes.reduce((sum, n) => sum + (n.data.actualTokens?.input || 0), 0);
      const totalActOut = executedNodes.reduce((sum, n) => sum + (n.data.actualTokens?.output || 0), 0);

      set({
        nodes: executedNodes,
        selectedNode: updatedSelectedNode || get().selectedNode,
        isExecuting: false,
        aggregates: {
          ...get().aggregates,
          actualTokens: {
            input: totalActIn,
            output: totalActOut,
            total: totalActIn + totalActOut
          }
        }
      });
      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'DAG execution failed';
      console.error('[Store] DAG execution error:', err);
      const failedNodes = get().nodes.map((node) => ({
        ...node,
        data: { ...node.data, executionStatus: 'failed', executionError: message }
      }));
      const currentSelectedId = get().selectedNode?.id;
      set({
        isExecuting: false,
        executionError: message,
        nodes: failedNodes,
        selectedNode: currentSelectedId ? failedNodes.find(n => n.id === currentSelectedId) || get().selectedNode : get().selectedNode
      });
      return null;
    }
  },

  executeNode: async (nodeId) => {
    const { nodes } = get();
    const targetNode = nodes.find(n => n.id === nodeId);
    if (!targetNode) return;

    const data = targetNode.data || {};
    const model = data.assignedAgent || data.recommendedAgent?.id || 'gemini-2-0-flash';
    const title = data.title || 'Untitled task';
    const description = data.description || '';

    const singleGraph = {
      [nodeId]: {
        prompt: description ? `${title}\n\n${description}` : title,
        model,
        depends_on: []
      }
    };

    const runningNodes = get().nodes.map(n => n.id === nodeId ? {
      ...n,
      data: { ...n.data, executionStatus: 'running', executionError: null }
    } : n);

    set({
      nodes: runningNodes,
      selectedNode: runningNodes.find(n => n.id === nodeId)
    });

    try {
      const res = await fetch(`${API_BASE}/api/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ graph: singleGraph })
      });
      const resData = await res.json();
      if (!res.ok) {
        throw new Error(resData.detail || `Execution failed with HTTP ${res.status}`);
      }
      const result = resData.results?.[nodeId];
      if (result) {
        const completedNodes = get().nodes.map(n => n.id === nodeId ? {
          ...n,
          data: {
            ...n.data,
            executionStatus: result.status,
            executionError: result.error,
            executionOutput: result.text,
            executionModel: result.routed_model || result.model,
            actualTokens: {
              input: result.prompt_tokens,
              output: result.completion_tokens,
              total: result.total_tokens
            }
          }
        } : n);
        set({
          nodes: completedNodes,
          selectedNode: completedNodes.find(n => n.id === nodeId)
        });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Task execution failed';
      const failedNodes = get().nodes.map(n => n.id === nodeId ? {
        ...n,
        data: { ...n.data, executionStatus: 'failed', executionError: msg }
      } : n);
      set({
        nodes: failedNodes,
        selectedNode: failedNodes.find(n => n.id === nodeId)
      });
    }
  },

  onNodesChange: (changes) => {
    set({
      nodes: applyNodeChanges(changes, get().nodes),
    });
  },

  onEdgesChange: (changes) => {
    set({
      edges: applyEdgeChanges(changes, get().edges),
    });
    // Trigger replan on edge removal/alteration
    get().replanGraph();
  },

  onConnect: (connection) => {
    const newEdges = addEdge(
      { ...connection, animated: true, style: { stroke: '#6366f1', strokeWidth: 2 } },
      get().edges
    );
    set({ edges: newEdges });
    get().replanGraph();
  },

  // Check Python ML Engine health
  checkHealth: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (res.ok) {
        set({ backendStatus: 'online' });
        return true;
      }
    } catch {
      set({ backendStatus: 'offline' });
    }
    return false;
  },

  // Decompose Goal into full DAG
  decomposeGoal: async (goal) => {
    const targetGoal = goal || get().goalInput;
    if (!targetGoal.trim()) return;

    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE}/api/decompose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal: targetGoal })
      });

      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const data = await res.json();

      set({
        nodes: data.nodes,
        edges: data.edges,
        aggregates: data.aggregates,
        selectedNode: data.nodes.length > 0 ? data.nodes[0] : null,
        isLoading: false,
        backendStatus: 'online'
      });
    } catch (err) {
      console.error('[Store] Failed to decompose goal:', err);
      set({ isLoading: false });
    }
  },

  // Real-time Replanning: updates tokenomics and recalculates DAG critical path
  replanGraph: async () => {
    const { nodes, edges } = get();
    if (nodes.length === 0) return;

    try {
      const res = await fetch(`${API_BASE}/api/replan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes, edges })
      });

      if (res.ok) {
        const data = await res.json();
        set({ aggregates: data.aggregates });
      }
    } catch (err) {
      console.error('[Store] Replan error:', err);
    }
  },

  // Human-in-the-loop: Update node title, prompt, or override assigned agent
  updateNodeData: async (nodeId, updatedFields) => {
    const { nodes } = get();
    
    // Check if title or description changed, in which case we re-run the ML forecaster
    const targetNode = nodes.find(n => n.id === nodeId);
    let newModelFields = {};

    if (
      targetNode && 
      (updatedFields.title && updatedFields.title !== targetNode.data.title ||
       updatedFields.description && updatedFields.description !== targetNode.data.description)
    ) {
      try {
        const title = updatedFields.title || targetNode.data.title;
        const desc = updatedFields.description || targetNode.data.description;
        const res = await fetch(`${API_BASE}/api/predict-node`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title,
            description: desc,
            upstream_count: targetNode.data.dependencies?.length || 0
          })
        });
        if (res.ok) {
          const pred = await res.json();
          newModelFields = {
            predictedTokens: pred.predictedTokens,
            complexityScore: pred.complexityScore,
            recommendedAgent: pred.recommendedAgent,
            modelEvaluations: pred.modelEvaluations
          };
        }
      } catch (e) {
        console.error('[Store] Predict node update error:', e);
      }
    }

    const updatedNodes = nodes.map(n => {
      if (n.id === nodeId) {
        const mergedData = {
          ...n.data,
          ...updatedFields,
          ...newModelFields
        };
        // If agent was explicitly overridden
        if (updatedFields.assignedAgent) {
          mergedData.assignedAgent = updatedFields.assignedAgent;
        }
        return { ...n, data: mergedData };
      }
      return n;
    });

    set({
      nodes: updatedNodes,
      selectedNode: updatedNodes.find(n => n.id === nodeId) || null
    });

    get().replanGraph();
  },

  // Add custom node with automated real-time token prediction
  addCustomNode: async (nodeData, parentId = null) => {
    const { nodes, edges } = get();
    const newId = `node-${Date.now()}`;

    // Predict tokenomics with local model
    let forecast = {
      predictedTokens: { input: 800, output: 1600, total: 2400 },
      complexityScore: 50,
      recommendedAgent: { id: 'gpt-4o', name: 'ChatGPT (GPT-4o)', color: '#10b981', estimatedCost: 0.018, estimatedLatency: 18.8 },
      modelEvaluations: {}
    };

    try {
      const res = await fetch(`${API_BASE}/api/predict-node`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: nodeData.title,
          description: nodeData.description,
          upstream_count: parentId ? 1 : 0
        })
      });
      if (res.ok) {
        forecast = await res.json();
      }
    } catch (e) {
      console.warn('[Store] Local prediction fallback on custom node add:', e);
    }

    // Determine canvas position relative to parent or center
    let position = { x: 300, y: 300 };
    if (parentId) {
      const parentNode = nodes.find(n => n.id === parentId);
      if (parentNode) {
        position = {
          x: parentNode.position.x + 360,
          y: parentNode.position.y + 40
        };
      }
    }

    const newNode = {
      id: newId,
      type: 'agentNode',
      position,
      data: {
        id: newId,
        title: nodeData.title,
        description: nodeData.description,
        category: nodeData.category || 'Custom Task',
        status: 'pending',
        dependencies: parentId ? [parentId] : [],
        predictedTokens: forecast.predictedTokens,
        complexityScore: forecast.complexityScore,
        recommendedAgent: forecast.recommendedAgent,
        assignedAgent: forecast.recommendedAgent.id,
        modelEvaluations: forecast.modelEvaluations
      }
    };

    const newNodes = [...nodes, newNode];
    let newEdges = [...edges];
    if (parentId) {
      newEdges.push({
        id: `e_${parentId}_${newId}`,
        source: parentId,
        target: newId,
        animated: true,
        style: { stroke: '#6366f1', strokeWidth: 2 }
      });
    }

    set({
      nodes: newNodes,
      edges: newEdges,
      selectedNode: newNode,
      isAddModalOpen: false,
      newSubtaskParentId: null
    });

    get().replanGraph();
  },

  // Remove node and prune downstream edges
  removeNode: (nodeId) => {
    const { nodes, edges, selectedNode } = get();
    const filteredNodes = nodes.filter(n => n.id !== nodeId);
    const filteredEdges = edges.filter(e => e.source !== nodeId && e.target !== nodeId);

    set({
      nodes: filteredNodes,
      edges: filteredEdges,
      selectedNode: selectedNode?.id === nodeId ? null : selectedNode
    });

    get().replanGraph();
  }
}));
