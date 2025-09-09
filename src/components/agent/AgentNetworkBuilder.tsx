import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Stack,
  Button,
  Typography,
  IconButton,
  Tooltip,
  Card,
  CardHeader,
  CardContent,
  Chip,
  Alert,
  Divider
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import DownloadIcon from '@mui/icons-material/Download';
import UploadIcon from '@mui/icons-material/Upload';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckOutlinedIcon from '@mui/icons-material/CheckOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { 
  Agent, 
  AgentConnection, 
  AgentNetwork, 
  AgentTemplate, 
  NetworkValidation,
  NetworkStatistics,
  AgentNetworkBuilderProps
} from '../../types/schema';
import {
  ConnectionType,
  AgentStatus,
  NetworkValidationStatus
} from '../../types/enums';
import { NetworkCanvas } from './NetworkCanvas';
import { AgentLibrary } from './AgentLibrary';
import { AgentConfigDialog } from './AgentConfigDialog';
import { formatNetworkComplexity } from '../../utils/formatters';

export const AgentNetworkBuilder: React.FC<AgentNetworkBuilderProps> = ({
  initialNetwork,
  availableTemplates,
  onNetworkChange,
  onExportNetwork,
  onValidationChange,
  readonly = false,
  maxAgents = 50,
  maxConnections = 100
}) => {
  const [network, setNetwork] = useState<AgentNetwork>(
    initialNetwork || {
      agents: [],
      connections: [],
      metadata: {
        name: 'New Agent Network',
        version: '1.0.0',
        created: new Date().toISOString(),
        lastModified: new Date().toISOString()
      }
    }
  );

  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [configDialogAgent, setConfigDialogAgent] = useState<Agent | null>(null);
  const [validation, setValidation] = useState<NetworkValidation>({
    status: NetworkValidationStatus.VALID,
    errors: [],
    warnings: [],
    suggestions: []
  });
  const [statistics, setStatistics] = useState<NetworkStatistics>({
    totalAgents: 0,
    totalConnections: 0,
    processingLayers: 0,
    complexity: 'Simple',
    cycleCount: 0,
    isolatedNodes: 0
  });

  // Validate network structure
  const validateNetwork = useCallback((networkToValidate: AgentNetwork): NetworkValidation => {
    const errors: string[] = [];
    const warnings: string[] = [];
    const suggestions: string[] = [];

    // Check for cycles (DAG validation)
    const hasCycles = detectCycles(networkToValidate);
    if (hasCycles) {
      errors.push('Network contains circular dependencies. DAG structure required.');
    }

    // Check for isolated nodes
    const isolatedNodes = findIsolatedNodes(networkToValidate);
    if (isolatedNodes.length > 0) {
      warnings.push(`${isolatedNodes.length} agent(s) have no connections.`);
    }

    // Check for missing configurations
    const misconfiguredAgents = networkToValidate.agents.filter(agent => 
      !agent.config.prompt || !agent.config.endpointUrl
    );
    if (misconfiguredAgents.length > 0) {
      errors.push(`${misconfiguredAgents.length} agent(s) have incomplete configuration.`);
    }

    // Performance suggestions
    if (networkToValidate.agents.length > 20) {
      suggestions.push('Consider breaking down large networks into smaller modules.');
    }

    if (networkToValidate.connections.length > networkToValidate.agents.length * 2) {
      suggestions.push('High connection density may impact performance.');
    }

    const status = errors.length > 0 ? NetworkValidationStatus.INVALID :
                  warnings.length > 0 ? NetworkValidationStatus.WARNING :
                  NetworkValidationStatus.VALID;

    return { status, errors, warnings, suggestions };
  }, []);

  // Detect cycles in the network
  const detectCycles = (networkToCheck: AgentNetwork): boolean => {
    const visited = new Set<string>();
    const recursionStack = new Set<string>();

    const dfs = (nodeId: string): boolean => {
      visited.add(nodeId);
      recursionStack.add(nodeId);

      const outgoingConnections = networkToCheck.connections.filter(
        conn => conn.sourceId === nodeId
      );

      for (const connection of outgoingConnections) {
        const targetId = connection.targetId;
        if (!visited.has(targetId)) {
          if (dfs(targetId)) return true;
        } else if (recursionStack.has(targetId)) {
          return true;
        }
      }

      recursionStack.delete(nodeId);
      return false;
    };

    for (const agent of networkToCheck.agents) {
      if (!visited.has(agent.id)) {
        if (dfs(agent.id)) return true;
      }
    }

    return false;
  };

  // Find isolated nodes
  const findIsolatedNodes = (networkToCheck: AgentNetwork): string[] => {
    return networkToCheck.agents
      .filter(agent => {
        const hasIncoming = networkToCheck.connections.some(conn => conn.targetId === agent.id);
        const hasOutgoing = networkToCheck.connections.some(conn => conn.sourceId === agent.id);
        return !hasIncoming && !hasOutgoing;
      })
      .map(agent => agent.id);
  };

  // Calculate network statistics
  const calculateStatistics = useCallback((networkToAnalyze: AgentNetwork): NetworkStatistics => {
    const totalAgents = networkToAnalyze.agents.length;
    const totalConnections = networkToAnalyze.connections.length;
    const complexity = formatNetworkComplexity(totalAgents, totalConnections);
    const cycleCount = detectCycles(networkToAnalyze) ? 1 : 0; // Simplified
    const isolatedNodes = findIsolatedNodes(networkToAnalyze).length;

    // Calculate processing layers (simplified topological sort)
    const processingLayers = calculateProcessingLayers(networkToAnalyze);

    return {
      totalAgents,
      totalConnections,
      processingLayers,
      complexity,
      cycleCount,
      isolatedNodes
    };
  }, []);

  const calculateProcessingLayers = (networkToAnalyze: AgentNetwork): number => {
    // Simplified layer calculation
    const inDegree = new Map<string, number>();
    
    // Initialize in-degrees
    networkToAnalyze.agents.forEach(agent => {
      inDegree.set(agent.id, 0);
    });

    // Calculate in-degrees
    networkToAnalyze.connections.forEach(conn => {
      inDegree.set(conn.targetId, (inDegree.get(conn.targetId) || 0) + 1);
    });

    let layers = 0;
    const remaining = new Set(networkToAnalyze.agents.map(a => a.id));

    while (remaining.size > 0) {
      const currentLayer = Array.from(remaining).filter(id => inDegree.get(id) === 0);
      
      if (currentLayer.length === 0) break; // Cycle detected or error
      
      currentLayer.forEach(id => {
        remaining.delete(id);
        networkToAnalyze.connections
          .filter(conn => conn.sourceId === id)
          .forEach(conn => {
            inDegree.set(conn.targetId, (inDegree.get(conn.targetId) || 0) - 1);
          });
      });
      
      layers++;
    }

    return layers;
  };

  // Update validation and statistics when network changes
  useEffect(() => {
    const newValidation = validateNetwork(network);
    const newStatistics = calculateStatistics(network);
    
    setValidation(newValidation);
    setStatistics(newStatistics);
    
    onValidationChange(newValidation);
    onNetworkChange(network);
  }, [network, validateNetwork, calculateStatistics, onValidationChange, onNetworkChange]);

  const handleAddAgent = useCallback((template: AgentTemplate) => {
    if (network.agents.length >= maxAgents) {
      alert(`Maximum of ${maxAgents} agents allowed`);
      return;
    }

    const newAgent: Agent = {
      id: `agent-${Date.now()}`,
      type: template.type,
      name: template.name,
      description: template.description,
      position: { 
        x: Math.random() * 400 + 100, 
        y: Math.random() * 300 + 100 
      },
      config: { ...template.defaultConfig },
      status: AgentStatus.ACTIVE,
      createdAt: new Date()
    };

    setNetwork(prev => ({
      ...prev,
      agents: [...prev.agents, newAgent],
      metadata: {
        ...prev.metadata,
        lastModified: new Date().toISOString()
      }
    }));
  }, [network.agents.length, maxAgents]);

  const handleAgentMove = useCallback((agentId: string, position: { x: number; y: number }) => {
    setNetwork(prev => ({
      ...prev,
      agents: prev.agents.map(agent =>
        agent.id === agentId ? { ...agent, position } : agent
      ),
      metadata: {
        ...prev.metadata,
        lastModified: new Date().toISOString()
      }
    }));
  }, []);

  const handleAgentDelete = useCallback((agentId: string) => {
    setNetwork(prev => ({
      ...prev,
      agents: prev.agents.filter(agent => agent.id !== agentId),
      connections: prev.connections.filter(
        conn => conn.sourceId !== agentId && conn.targetId !== agentId
      ),
      metadata: {
        ...prev.metadata,
        lastModified: new Date().toISOString()
      }
    }));
  }, []);

  const handleAgentDuplicate = useCallback((agentId: string) => {
    const agent = network.agents.find(a => a.id === agentId);
    if (!agent) return;

    const duplicatedAgent: Agent = {
      ...agent,
      id: `agent-${Date.now()}`,
      name: `${agent.name} (Copy)`,
      position: {
        x: agent.position.x + 50,
        y: agent.position.y + 50
      },
      createdAt: new Date()
    };

    setNetwork(prev => ({
      ...prev,
      agents: [...prev.agents, duplicatedAgent],
      metadata: {
        ...prev.metadata,
        lastModified: new Date().toISOString()
      }
    }));
  }, [network.agents]);

  const handleAgentSave = useCallback((updatedAgent: Agent) => {
    setNetwork(prev => ({
      ...prev,
      agents: prev.agents.map(agent =>
        agent.id === updatedAgent.id ? updatedAgent : agent
      ),
      metadata: {
        ...prev.metadata,
        lastModified: new Date().toISOString()
      }
    }));
  }, []);

  const handleExportNetwork = () => {
    onExportNetwork(network);
  };

  const getValidationIcon = () => {
    switch (validation.status) {
      case NetworkValidationStatus.VALID:
        return <CheckOutlinedIcon className="text-success-main" />;
      case NetworkValidationStatus.WARNING:
        return <WarningAmberIcon className="text-warning-main" />;
      case NetworkValidationStatus.INVALID:
        return <ErrorOutlineIcon className="text-error-main" />;
      default:
        return <RefreshIcon className="animate-spin" />;
    }
  };

  return (
    <Box className="h-full flex flex-col">
      {/* Header */}
      <Card className="mb-4">
        <CardHeader
          title={
            <Stack direction="row" alignItems="center" justifyContent="space-between">
              <Typography variant="h5">
                Agent Network Builder
              </Typography>
              <Stack direction="row" spacing={1} alignItems="center">
                {getValidationIcon()}
                <Typography variant="body2" color="text.secondary">
                  {validation.status}
                </Typography>
              </Stack>
            </Stack>
          }
          action={
            <Stack direction="row" spacing={1}>
              <Tooltip title="Export Network">
                <IconButton onClick={handleExportNetwork}>
                  <DownloadIcon />
                </IconButton>
              </Tooltip>
              <Button
                variant="contained"
                startIcon={<SaveIcon />}
                onClick={handleExportNetwork}
                disabled={validation.status === NetworkValidationStatus.INVALID}
              >
                Save Network
              </Button>
            </Stack>
          }
        />
      </Card>

      {/* Validation Messages */}
      {validation.errors.length > 0 && (
        <Alert severity="error" className="mb-4">
          <Typography variant="subtitle2">Validation Errors:</Typography>
          <ul className="mt-1 ml-4">
            {validation.errors.map((error, index) => (
              <li key={index}>{error}</li>
            ))}
          </ul>
        </Alert>
      )}

      {validation.warnings.length > 0 && (
        <Alert severity="warning" className="mb-4">
          <Typography variant="subtitle2">Warnings:</Typography>
          <ul className="mt-1 ml-4">
            {validation.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </Alert>
      )}

      {/* Main Content */}
      <Box className="flex-1 flex gap-4 min-h-0">
        {/* Agent Library */}
        <Box className="w-80 h-full min-h-0">
          <AgentLibrary
            templates={availableTemplates}
            onAddAgent={handleAddAgent}
          />
        </Box>

        {/* Network Canvas */}
        <Box className="flex-1 min-h-0">
          <NetworkCanvas
            agents={network.agents}
            connections={network.connections}
            selectedAgentId={selectedAgentId}
            onAgentSelect={setSelectedAgentId}
            onAgentConfigure={setConfigDialogAgent}
            onAgentDelete={handleAgentDelete}
            onAgentDuplicate={handleAgentDuplicate}
            onAgentMove={handleAgentMove}
            onConnectionCreate={() => {}} // TODO: Implement connection creation
            readonly={readonly}
          />
        </Box>

        {/* Statistics Panel */}
        <Box className="w-80 h-full min-h-0">
          <Card className="h-full">
            <CardHeader title="Network Statistics" />
            <CardContent>
              <Stack spacing={3}>
                <Box className="grid grid-cols-2 gap-4">
                  <Box className="text-center">
                    <Typography variant="h4" color="primary.main">
                      {statistics.totalAgents}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Agents
                    </Typography>
                  </Box>
                  <Box className="text-center">
                    <Typography variant="h4" color="secondary.main">
                      {statistics.totalConnections}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Connections
                    </Typography>
                  </Box>
                </Box>

                <Divider />

                <Stack spacing={2}>
                  <Box className="flex justify-between">
                    <Typography variant="body2">Complexity:</Typography>
                    <Chip label={statistics.complexity} size="small" />
                  </Box>
                  <Box className="flex justify-between">
                    <Typography variant="body2">Processing Layers:</Typography>
                    <Typography variant="body2">{statistics.processingLayers}</Typography>
                  </Box>
                  <Box className="flex justify-between">
                    <Typography variant="body2">Isolated Nodes:</Typography>
                    <Typography variant="body2" color={statistics.isolatedNodes > 0 ? 'warning.main' : 'text.primary'}>
                      {statistics.isolatedNodes}
                    </Typography>
                  </Box>
                </Stack>

                <Divider />

                <Box>
                  <Typography variant="subtitle2" className="mb-2">Network Health</Typography>
                  <Box className="w-full bg-grey-700 rounded-full h-2">
                    <Box
                      className="bg-success-main h-2 rounded-full transition-all"
                      style={{
                        width: `${validation.status === NetworkValidationStatus.VALID ? 100 :
                               validation.status === NetworkValidationStatus.WARNING ? 70 : 30}%`
                      }}
                    />
                  </Box>
                  <Typography variant="caption" color="text.secondary" className="mt-1 block">
                    {validation.status === NetworkValidationStatus.VALID ? 'Excellent' :
                     validation.status === NetworkValidationStatus.WARNING ? 'Good' : 'Needs Attention'}
                  </Typography>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Box>
      </Box>

      {/* Agent Configuration Dialog */}
      <AgentConfigDialog
        open={!!configDialogAgent}
        agent={configDialogAgent}
        onClose={() => setConfigDialogAgent(null)}
        onSave={handleAgentSave}
      />
    </Box>
  );
};