import React, { useState, useRef, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Tooltip,
  Stack
} from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong';
import { Agent, AgentConnection } from '../../types/schema';
import { ConnectionType } from '../../types/enums';
import { AgentNode } from './AgentNode';

interface NetworkCanvasProps {
  agents: Agent[];
  connections: AgentConnection[];
  selectedAgentId: string | null;
  onAgentSelect: (agentId: string) => void;
  onAgentConfigure: (agent: Agent) => void;
  onAgentDelete: (agentId: string) => void;
  onAgentDuplicate: (agentId: string) => void;
  onAgentMove: (agentId: string, position: { x: number; y: number }) => void;
  onConnectionCreate: (sourceId: string, targetId: string) => void;
  readonly?: boolean;
}

export const NetworkCanvas: React.FC<NetworkCanvasProps> = ({
  agents,
  connections,
  selectedAgentId,
  onAgentSelect,
  onAgentConfigure,
  onAgentDelete,
  onAgentDuplicate,
  onAgentMove,
  onConnectionCreate,
  readonly = false
}) => {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [draggedAgent, setDraggedAgent] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLDivElement>(null);

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.1, 2));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.1, 0.5));
  };

  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleAgentDragStart = useCallback((agentId: string, e: React.MouseEvent, initialPos: { x: number; y: number }) => {
    if (readonly) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (rect) {
      // Calculate cursor offset within the agent card in transformed coords
      const offsetX = e.clientX - rect.left - (initialPos.x + pan.x) * zoom;
      const offsetY = e.clientY - rect.top - (initialPos.y + pan.y) * zoom;
      setDragOffset({ x: offsetX, y: offsetY });
    }
    setDraggedAgent(agentId);
    setIsDragging(true);
  }, [readonly, pan.x, pan.y, zoom]);

  const handleAgentDragEnd = useCallback(() => {
    setDraggedAgent(null);
    setIsDragging(false);
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (draggedAgent && isDragging) {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (rect) {
        const newPosition = {
          x: (e.clientX - rect.left - dragOffset.x) / zoom - pan.x,
          y: (e.clientY - rect.top - dragOffset.y) / zoom - pan.y
        };
        onAgentMove(draggedAgent, newPosition);
      }
    }
  }, [draggedAgent, isDragging, dragOffset, zoom, pan, onAgentMove]);

  const getConnectionColor = (type: ConnectionType): string => {
    switch (type) {
      case ConnectionType.INFORMATION_FLOW:
        return '#4FC3F7';
      case ConnectionType.DEPENDENCY:
        return '#FF5722';
      case ConnectionType.FEEDBACK:
        return '#4CAF50';
      case ConnectionType.TRIGGER:
        return '#FF9800';
      default:
        return '#607D8B';
    }
  };

  const getConnectionStyle = (type: ConnectionType): string => {
    switch (type) {
      case ConnectionType.DEPENDENCY:
        return '5,5';
      case ConnectionType.FEEDBACK:
        return '10,5';
      default:
        return 'none';
    }
  };

  const renderConnection = (connection: AgentConnection) => {
    const sourceAgent = agents.find(a => a.id === connection.sourceId);
    const targetAgent = agents.find(a => a.id === connection.targetId);

    if (!sourceAgent || !targetAgent) return null;

    const sourceX = sourceAgent.position.x + 125; // Center of agent node
    const sourceY = sourceAgent.position.y + 75;
    const targetX = targetAgent.position.x + 125;
    const targetY = targetAgent.position.y + 75;

    // Calculate arrow position
    const angle = Math.atan2(targetY - sourceY, targetX - sourceX);
    const arrowX = targetX - Math.cos(angle) * 20;
    const arrowY = targetY - Math.sin(angle) * 20;

    return (
      <g key={connection.id}>
        {/* Connection line */}
        <line
          x1={sourceX}
          y1={sourceY}
          x2={arrowX}
          y2={arrowY}
          stroke={getConnectionColor(connection.type)}
          strokeWidth={connection.strength * 3}
          strokeOpacity={0.8}
          strokeDasharray={getConnectionStyle(connection.type)}
          markerEnd="url(#arrowhead)"
        />
        
        {/* Connection label */}
        <text
          x={(sourceX + targetX) / 2}
          y={(sourceY + targetY) / 2 - 10}
          fill="currentColor"
          fontSize="10"
          textAnchor="middle"
          className="text-text-secondary"
        >
          {connection.type.replace('_', ' ')}
        </text>
      </g>
    );
  };

  return (
    <Paper className="relative w-full h-full overflow-hidden bg-grey-900">
      {/* Canvas Controls */}
      <Box className="absolute top-4 right-4 z-10">
        <Stack direction="row" spacing={1}>
          <Tooltip title="Zoom In">
            <IconButton onClick={handleZoomIn} size="small" className="bg-background-paper">
              <ZoomInIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Zoom Out">
            <IconButton onClick={handleZoomOut} size="small" className="bg-background-paper">
              <ZoomOutIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Reset View">
            <IconButton onClick={handleResetView} size="small" className="bg-background-paper">
              <CenterFocusStrongIcon />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      {/* Zoom Level Indicator */}
      <Box className="absolute top-4 left-4 z-10 bg-background-paper rounded px-2 py-1">
        <Typography variant="caption">
          Zoom: {Math.round(zoom * 100)}%
        </Typography>
      </Box>

      {/* Canvas */}
      <Box
        ref={canvasRef}
        className="w-full h-full relative cursor-move"
        style={{
          transform: `scale(${zoom}) translate(${pan.x}px, ${pan.y}px)`,
          transformOrigin: '0 0'
        }}
        onMouseMove={handleMouseMove}
        onMouseUp={handleAgentDragEnd}
      >
        {/* Grid Background */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ minWidth: '2000px', minHeight: '2000px' }}
        >
          <defs>
            <pattern
              id="grid"
              width="20"
              height="20"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 20 0 L 0 0 0 20"
                fill="none"
                stroke="rgba(139, 69, 19, 0.2)"
                strokeWidth="1"
              />
            </pattern>
            
            {/* Arrow marker for connections */}
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon
                points="0 0, 10 3.5, 0 7"
                fill="currentColor"
              />
            </marker>
          </defs>
          
          <rect width="100%" height="100%" fill="url(#grid)" />
          
          {/* Render connections */}
          {connections.map(renderConnection)}
        </svg>

        {/* Agent Nodes */}
        {agents.map((agent) => (
          <AgentNode
            key={agent.id}
            agent={agent}
            isSelected={selectedAgentId === agent.id}
            isDragging={draggedAgent === agent.id}
            onSelect={onAgentSelect}
            onConfigure={onAgentConfigure}
            onDelete={onAgentDelete}
            onDuplicate={onAgentDuplicate}
            onDragStart={handleAgentDragStart}
            onDragEnd={handleAgentDragEnd}
            style={{
              position: 'absolute',
              left: agent.position.x,
              top: agent.position.y,
              zIndex: selectedAgentId === agent.id ? 10 : 1
            }}
          />
        ))}

        {/* Empty State */}
        {agents.length === 0 && (
          <Box className="absolute inset-0 flex items-center justify-center">
            <Stack alignItems="center" spacing={2}>
              <Typography variant="h6" color="text.secondary">
                No agents in network
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Drag agents from the library to start building your network
              </Typography>
            </Stack>
          </Box>
        )}
      </Box>
    </Paper>
  );
};