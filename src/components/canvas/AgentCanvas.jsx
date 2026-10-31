import React, { useMemo, useCallback } from 'react';
import { 
  ReactFlow, 
  MiniMap, 
  Controls, 
  Background, 
  BackgroundVariant 
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useDagStore } from '../../store/useDagStore';
import { CustomTaskNode } from './CustomTaskNode';

export const AgentCanvas = () => {
  const { 
    nodes, 
    edges, 
    onNodesChange, 
    onEdgesChange, 
    onConnect, 
    setSelectedNode 
  } = useDagStore();

  const nodeTypes = useMemo(() => ({
    agentNode: CustomTaskNode,
  }), []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, [setSelectedNode]);

  return (
    <div className="canvas-area">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        onPaneClick={onPaneClick}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.2}
        maxZoom={2.0}
        defaultEdgeOptions={{
          animated: true,
          style: { stroke: '#6366f1', strokeWidth: 2 },
        }}
      >
        <Background 
          variant={BackgroundVariant.Dots} 
          gap={24} 
          size={1.5} 
          color="rgba(255, 255, 255, 0.07)" 
        />
        <Controls 
          showInteractive={false} 
          position="bottom-left" 
        />
        <MiniMap 
          nodeStrokeColor="#6366f1"
          nodeColor="#1e293b"
          nodeBorderRadius={6}
          maskColor="rgba(7, 9, 14, 0.75)"
          position="bottom-right"
          style={{
            background: 'rgba(13, 18, 31, 0.85)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 10,
            overflow: 'hidden'
          }}
        />
      </ReactFlow>
    </div>
  );
};
