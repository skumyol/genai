import React, { useState } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Stack,
  Button,
  Chip,
  Box,
  IconButton,
  Tooltip
} from '@mui/material';
import DeviceHubOutlinedIcon from '@mui/icons-material/DeviceHubOutlined';
import SendOutlinedIcon from '@mui/icons-material/SendOutlined';
import RefreshOutlinedIcon from '@mui/icons-material/RefreshOutlined';
import { NPC } from '../../types/schema';

interface NetworkDiagramProps {
  npcs: NPC[];
  onSendToServer?: (networkData: any) => void;
}

interface Connection {
  from: string;
  to: string;
  strength: number;
  type: 'direct' | 'indirect' | 'weak';
}

export const NetworkDiagram: React.FC<NetworkDiagramProps> = ({ 
  npcs, 
  onSendToServer 
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  // Generate mock connections between NPCs
  const generateConnections = (): Connection[] => {
    const connections: Connection[] = [];
    const npcIds = npcs.map(npc => npc.id);
    
    // Create some realistic connections
    const connectionPatterns = [
      { from: 'npc-1', to: 'npc-5', strength: 0.9, type: 'direct' as const }, // Knight to Noble
      { from: 'npc-2', to: 'npc-4', strength: 0.7, type: 'indirect' as const }, // Sorceress to Monk
      { from: 'npc-3', to: 'npc-1', strength: 0.6, type: 'weak' as const }, // Merchant to Knight
      { from: 'npc-3', to: 'npc-5', strength: 0.8, type: 'direct' as const }, // Merchant to Noble
      { from: 'npc-4', to: 'npc-1', strength: 0.5, type: 'weak' as const }, // Monk to Knight
    ];
    
    return connectionPatterns.filter(conn => 
      npcIds.includes(conn.from) && npcIds.includes(conn.to)
    );
  };

  const [connections] = useState<Connection[]>(generateConnections());

  const getConnectionColor = (type: string) => {
    switch (type) {
      case 'direct':
        return 'success';
      case 'indirect':
        return 'warning';
      default:
        return 'error';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return '#4CAF50';
      case 'busy':
        return '#FF9800';
      default:
        return '#F44336';
    }
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
    }, 1000);
  };

  const handleSendToServer = () => {
    const networkData = {
      timestamp: new Date().toISOString(),
      nodes: npcs.map(npc => ({
        id: npc.id,
        name: npc.name,
        status: npc.status,
        type: 'npc'
      })),
      connections: connections.map(conn => ({
        source: conn.from,
        target: conn.to,
        strength: conn.strength,
        type: conn.type
      })),
      metadata: {
        totalNodes: npcs.length,
        totalConnections: connections.length,
        networkHealth: connections.filter(c => c.type === 'direct').length / connections.length
      }
    };

    console.log('Sending network data to server:', networkData);
    onSendToServer?.(networkData);
  };

  return (
    <Card className="medieval-shadow">
      <CardHeader 
        title={
          <Stack direction="row" alignItems="center" spacing={1}>
            <DeviceHubOutlinedIcon className="text-primary-main" />
            <Typography variant="h6">
              NPC Agent Network
            </Typography>
          </Stack>
        }
        action={
          <Stack direction="row" spacing={1}>
            <Tooltip title="Refresh Network">
              <IconButton 
                onClick={handleRefresh} 
                disabled={isRefreshing}
                size="small"
              >
                <RefreshOutlinedIcon className={isRefreshing ? 'animate-spin' : ''} />
              </IconButton>
            </Tooltip>
            <Button
              variant="contained"
              size="small"
              startIcon={<SendOutlinedIcon />}
              onClick={handleSendToServer}
              color="secondary"
            >
              Send to Server
            </Button>
          </Stack>
        }
      />
      <CardContent>
        <Stack spacing={3}>
          {/* Network Visualization */}
          <Box className="relative bg-grey-900 rounded-lg p-6 min-h-[300px] overflow-hidden">
            {/* Background grid pattern */}
            <div 
              className="absolute inset-0 opacity-20"
              style={{
                backgroundImage: `
                  linear-gradient(rgba(139, 69, 19, 0.3) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(139, 69, 19, 0.3) 1px, transparent 1px)
                `,
                backgroundSize: '20px 20px'
              }}
            />
            
            {/* NPC Nodes */}
            <div className="relative">
              {npcs.map((npc, index) => {
                const angle = (index / npcs.length) * 2 * Math.PI;
                const radius = 100;
                const x = 150 + radius * Math.cos(angle);
                const y = 150 + radius * Math.sin(angle);
                
                return (
                  <div
                    key={npc.id}
                    className="absolute transform -translate-x-1/2 -translate-y-1/2"
                    style={{ left: x, top: y }}
                  >
                    <Tooltip title={`${npc.name} - ${npc.status}`}>
                      <div 
                        className="w-12 h-12 rounded-full border-2 flex items-center justify-center cursor-pointer transition-all hover:scale-110"
                        style={{ 
                          backgroundColor: getStatusColor(npc.status),
                          borderColor: getStatusColor(npc.status)
                        }}
                      >
                        <Typography variant="caption" className="text-white font-bold">
                          {npc.name.split(' ')[0].charAt(0)}
                        </Typography>
                      </div>
                    </Tooltip>
                  </div>
                );
              })}
              
              {/* Connection Lines */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none">
                {connections.map((conn, index) => {
                  const fromIndex = npcs.findIndex(npc => npc.id === conn.from);
                  const toIndex = npcs.findIndex(npc => npc.id === conn.to);
                  
                  if (fromIndex === -1 || toIndex === -1) return null;
                  
                  const fromAngle = (fromIndex / npcs.length) * 2 * Math.PI;
                  const toAngle = (toIndex / npcs.length) * 2 * Math.PI;
                  const radius = 100;
                  
                  const x1 = 150 + radius * Math.cos(fromAngle);
                  const y1 = 150 + radius * Math.sin(fromAngle);
                  const x2 = 150 + radius * Math.cos(toAngle);
                  const y2 = 150 + radius * Math.sin(toAngle);
                  
                  const strokeColor = conn.type === 'direct' ? '#4CAF50' : 
                                   conn.type === 'indirect' ? '#FF9800' : '#F44336';
                  
                  return (
                    <line
                      key={index}
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke={strokeColor}
                      strokeWidth={conn.strength * 3}
                      strokeOpacity={0.7}
                      strokeDasharray={conn.type === 'weak' ? '5,5' : 'none'}
                    />
                  );
                })}
              </svg>
            </div>
          </Box>

          {/* Network Statistics */}
          <Stack spacing={2}>
            <Typography variant="subtitle2" color="text.secondary">
              Network Statistics
            </Typography>
            <Box className="grid grid-cols-2 gap-4">
              <div className="text-center">
                <Typography variant="h4" color="primary.main">
                  {npcs.length}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Active Agents
                </Typography>
              </div>
              <div className="text-center">
                <Typography variant="h4" color="secondary.main">
                  {connections.length}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Connections
                </Typography>
              </div>
            </Box>
          </Stack>

          {/* Connection Types Legend */}
          <Stack spacing={1}>
            <Typography variant="subtitle2" color="text.secondary">
              Connection Types
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip 
                label="Direct" 
                color="success" 
                size="small" 
                variant="outlined"
              />
              <Chip 
                label="Indirect" 
                color="warning" 
                size="small" 
                variant="outlined"
              />
              <Chip 
                label="Weak" 
                color="error" 
                size="small" 
                variant="outlined"
              />
            </Stack>
          </Stack>

          {/* Network Health */}
          <Box className="p-3 bg-primary-main/10 rounded-lg border border-primary-main/30">
            <Typography variant="body2" color="primary.main" className="font-semibold mb-1">
              🌐 Network Health: {Math.round((connections.filter(c => c.type === 'direct').length / connections.length) * 100)}%
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Based on direct connections between agents. Higher values indicate better network stability.
            </Typography>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
};