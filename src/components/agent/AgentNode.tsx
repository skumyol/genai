import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  Box,
  Stack
} from '@mui/material';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { Agent } from '../../types/schema';
import { AgentStatus, AgentType } from '../../types/enums';
import { formatAgentType, formatAgentStatus } from '../../utils/formatters';

interface AgentNodeProps {
  agent: Agent;
  isSelected: boolean;
  isDragging: boolean;
  onSelect: (agentId: string) => void;
  onConfigure: (agent: Agent) => void;
  onDelete: (agentId: string) => void;
  onDuplicate: (agentId: string) => void;
  onDragStart: (agentId: string, e: React.MouseEvent, position: { x: number; y: number }) => void;
  onDragEnd: () => void;
  style?: React.CSSProperties;
}

export const AgentNode: React.FC<AgentNodeProps> = ({
  agent,
  isSelected,
  isDragging,
  onSelect,
  onConfigure,
  onDelete,
  onDuplicate,
  onDragStart,
  onDragEnd,
  style
}) => {
  const [isHovered, setIsHovered] = useState(false);

  const getAgentTypeColor = (type: AgentType): string => {
    switch (type) {
      case AgentType.NPC_MANAGER:
        return '#8B4513';
      case AgentType.OPINION:
        return '#9C27B0';
      case AgentType.REPUTATION:
        return '#FF5722';
      case AgentType.SOCIAL_STANCE:
        return '#2196F3';
      case AgentType.MEMORY:
        return '#4CAF50';
      case AgentType.CONTEXT:
        return '#FF9800';
      default:
        return '#607D8B';
    }
  };

  const getStatusColor = (status: AgentStatus) => {
    switch (status) {
      case AgentStatus.ACTIVE:
        return 'success';
      case AgentStatus.PROCESSING:
        return 'warning';
      case AgentStatus.ERROR:
        return 'error';
      default:
        return 'default';
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0) { // Left click
      onSelect(agent.id);
      e.preventDefault();
      onDragStart(agent.id, e, agent.position);
    }
  };

  const handleMouseUp = () => {
    onDragEnd();
  };

  return (
    <Card
      className={`transition-all duration-200 cursor-move ${
        isSelected ? 'ring-2 ring-primary-main' : ''
      } ${isDragging ? 'opacity-50 scale-105' : ''} ${
        isHovered ? 'shadow-lg scale-102' : ''
      }`}
      style={{
        ...style,
        borderColor: getAgentTypeColor(agent.type),
        borderWidth: 2,
        borderStyle: 'solid',
        minWidth: 200,
        maxWidth: 250
      }}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <CardContent className="p-3">
        <Stack spacing={2}>
          {/* Agent Header */}
          <Box className="flex items-center justify-between">
            <Box 
              className="w-4 h-4 rounded-full"
              style={{ backgroundColor: getAgentTypeColor(agent.type) }}
            />
            <Stack direction="row" spacing={0.5}>
              <Tooltip title="Configure Agent">
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    onConfigure(agent);
                  }}
                >
                  <SettingsOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Duplicate Agent">
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDuplicate(agent.id);
                  }}
                >
                  <ContentCopyIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Delete Agent">
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(agent.id);
                  }}
                >
                  <DeleteOutlineIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Stack>
          </Box>

          {/* Agent Info */}
          <Box>
            <Typography variant="subtitle1" className="font-semibold mb-1">
              {agent.name}
            </Typography>
            <Typography variant="caption" color="text.secondary" className="block mb-2">
              {formatAgentType(agent.type)}
            </Typography>
            {agent.description && (
              <Typography variant="body2" color="text.secondary" className="text-xs">
                {agent.description}
              </Typography>
            )}
          </Box>

          {/* Agent Status */}
          <Box className="flex items-center justify-between">
            <Chip
              label={formatAgentStatus(agent.status)}
              color={getStatusColor(agent.status)}
              size="small"
              variant="outlined"
            />
            <Typography variant="caption" color="text.secondary">
              {agent.config.model}
            </Typography>
          </Box>

          {/* Connection Points */}
          <Box className="flex justify-between items-center">
            <Box className="flex space-x-1">
              <Tooltip title="Input Connection Point">
                <Box 
                  className="w-3 h-3 rounded-full border-2 border-primary-main bg-background-paper cursor-pointer hover:bg-primary-main transition-colors"
                />
              </Tooltip>
            </Box>
            <Box className="flex space-x-1">
              <Tooltip title="Output Connection Point">
                <Box 
                  className="w-3 h-3 rounded-full border-2 border-secondary-main bg-background-paper cursor-pointer hover:bg-secondary-main transition-colors"
                />
              </Tooltip>
            </Box>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
};