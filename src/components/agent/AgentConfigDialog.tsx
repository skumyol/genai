import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Stack,
  IconButton,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Divider,
  Box,
  Chip
} from '@mui/material';
import CloseOutlinedIcon from '@mui/icons-material/CloseOutlined';
import SettingsApplicationsOutlinedIcon from '@mui/icons-material/SettingsApplicationsOutlined';
import { Agent, AgentConfig } from '../../types/schema';
import { AgentType, LLMProvider } from '../../types/enums';
import { formatAgentType, formatLLMProvider } from '../../utils/formatters';

interface AgentConfigDialogProps {
  open: boolean;
  agent: Agent | null;
  onClose: () => void;
  onSave: (agent: Agent) => void;
}

export const AgentConfigDialog: React.FC<AgentConfigDialogProps> = ({
  open,
  agent,
  onClose,
  onSave
}) => {
  const [config, setConfig] = useState<AgentConfig>({
    prompt: '',
    llmProvider: LLMProvider.OPENAI,
    model: 'gpt-4',
    endpointUrl: '',
    memorySize: 1000,
    temperature: 0.7,
    maxTokens: 2000,
    timeout: 30000
  });

  const [agentInfo, setAgentInfo] = useState({
    name: '',
    description: '',
    type: AgentType.CUSTOM
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (agent) {
      setConfig(agent.config);
      setAgentInfo({
        name: agent.name,
        description: agent.description || '',
        type: agent.type
      });
    }
  }, [agent]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!agentInfo.name.trim()) {
      newErrors.name = 'Agent name is required';
    }

    if (!config.prompt.trim()) {
      newErrors.prompt = 'Prompt is required';
    }

    if (!config.endpointUrl.trim()) {
      newErrors.endpointUrl = 'Endpoint URL is required';
    }

    if (config.memorySize < 100) {
      newErrors.memorySize = 'Memory size must be at least 100';
    }

    if (config.temperature < 0 || config.temperature > 2) {
      newErrors.temperature = 'Temperature must be between 0 and 2';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = () => {
    if (!validateForm() || !agent) return;

    const updatedAgent: Agent = {
      ...agent,
      name: agentInfo.name,
      description: agentInfo.description,
      type: agentInfo.type,
      config,
      lastModified: new Date()
    };

    onSave(updatedAgent);
    onClose();
  };

  const handleConfigChange = (field: keyof AgentConfig, value: any) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleAgentInfoChange = (field: string, value: any) => {
    setAgentInfo(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const getModelOptions = (provider: LLMProvider): string[] => {
    switch (provider) {
      case LLMProvider.OPENAI:
        return ['gpt-4', 'gpt-3.5-turbo', 'gpt-4-turbo'];
      case LLMProvider.ANTHROPIC:
        return ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'];
      case LLMProvider.GOOGLE:
        return ['gemini-pro', 'gemini-pro-vision'];
      default:
        return ['custom-model'];
    }
  };

  if (!agent) return null;

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      maxWidth="md"
      fullWidth
      className="backdrop-blur-sm"
    >
      <DialogTitle>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" alignItems="center" spacing={1}>
            <SettingsApplicationsOutlinedIcon />
            <Typography variant="h2">
              Configure Agent
            </Typography>
          </Stack>
          <IconButton onClick={onClose} size="small">
            <CloseOutlinedIcon />
          </IconButton>
        </Stack>
      </DialogTitle>

      <DialogContent>
        <Stack spacing={3} className="mt-2">
          {/* Basic Information */}
          <Box>
            <Typography variant="h6" className="mb-3">Basic Information</Typography>
            <Stack spacing={2}>
              <TextField
                label="Agent Name"
                value={agentInfo.name}
                onChange={(e) => handleAgentInfoChange('name', e.target.value)}
                fullWidth
                error={!!errors.name}
                helperText={errors.name}
                required
              />
              
              <TextField
                label="Description"
                value={agentInfo.description}
                onChange={(e) => handleAgentInfoChange('description', e.target.value)}
                fullWidth
                multiline
                rows={2}
                placeholder="Brief description of the agent's purpose..."
              />

              <FormControl fullWidth>
                <InputLabel>Agent Type</InputLabel>
                <Select
                  value={agentInfo.type}
                  onChange={(e) => handleAgentInfoChange('type', e.target.value)}
                  label="Agent Type"
                >
                  {Object.values(AgentType).map((type) => (
                    <MenuItem key={type} value={type}>
                      {formatAgentType(type)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>
          </Box>

          <Divider />

          {/* LLM Configuration */}
          <Box>
            <Typography variant="h6" className="mb-3">LLM Configuration</Typography>
            <Stack spacing={2}>
              <TextField
                label="System Prompt"
                value={config.prompt}
                onChange={(e) => handleConfigChange('prompt', e.target.value)}
                fullWidth
                multiline
                rows={4}
                error={!!errors.prompt}
                helperText={errors.prompt || 'Define the agent\'s behavior and role'}
                required
              />

              <Box className="grid grid-cols-2 gap-4">
                <FormControl fullWidth>
                  <InputLabel>LLM Provider</InputLabel>
                  <Select
                    value={config.llmProvider}
                    onChange={(e) => handleConfigChange('llmProvider', e.target.value)}
                    label="LLM Provider"
                  >
                    {Object.values(LLMProvider).map((provider) => (
                      <MenuItem key={provider} value={provider}>
                        {formatLLMProvider(provider)}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <FormControl fullWidth>
                  <InputLabel>Model</InputLabel>
                  <Select
                    value={config.model}
                    onChange={(e) => handleConfigChange('model', e.target.value)}
                    label="Model"
                  >
                    {getModelOptions(config.llmProvider).map((model) => (
                      <MenuItem key={model} value={model}>
                        {model}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>

              <TextField
                label="Endpoint URL"
                value={config.endpointUrl}
                onChange={(e) => handleConfigChange('endpointUrl', e.target.value)}
                fullWidth
                error={!!errors.endpointUrl}
                helperText={errors.endpointUrl || 'API endpoint for this agent'}
                required
              />
            </Stack>
          </Box>

          <Divider />

          {/* Advanced Settings */}
          <Box>
            <Typography variant="h6" className="mb-3">Advanced Settings</Typography>
            <Stack spacing={3}>
              <Box>
                <Typography variant="body2" className="mb-2">
                  Temperature: {config.temperature}
                </Typography>
                <Slider
                  value={config.temperature}
                  onChange={(_, value) => handleConfigChange('temperature', value)}
                  min={0}
                  max={2}
                  step={0.1}
                  marks={[
                    { value: 0, label: '0' },
                    { value: 1, label: '1' },
                    { value: 2, label: '2' }
                  ]}
                  valueLabelDisplay="auto"
                />
                <Typography variant="caption" color="text.secondary">
                  Controls randomness in responses (0 = deterministic, 2 = very random)
                </Typography>
              </Box>

              <Box>
                <Typography variant="body2" className="mb-2">
                  Memory Size: {config.memorySize} tokens
                </Typography>
                <Slider
                  value={config.memorySize}
                  onChange={(_, value) => handleConfigChange('memorySize', value)}
                  min={100}
                  max={5000}
                  step={100}
                  marks={[
                    { value: 100, label: '100' },
                    { value: 2500, label: '2.5K' },
                    { value: 5000, label: '5K' }
                  ]}
                  valueLabelDisplay="auto"
                />
              </Box>

              <Box className="grid grid-cols-2 gap-4">
                <TextField
                  label="Max Tokens"
                  type="number"
                  value={config.maxTokens || ''}
                  onChange={(e) => handleConfigChange('maxTokens', parseInt(e.target.value) || undefined)}
                  helperText="Maximum response length"
                />

                <TextField
                  label="Timeout (ms)"
                  type="number"
                  value={config.timeout || ''}
                  onChange={(e) => handleConfigChange('timeout', parseInt(e.target.value) || undefined)}
                  helperText="Request timeout"
                />
              </Box>
            </Stack>
          </Box>

          {/* Configuration Preview */}
          <Box className="p-3 bg-grey-900 rounded-lg">
            <Typography variant="subtitle2" className="mb-2">Configuration Summary</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip label={formatLLMProvider(config.llmProvider)} size="small" />
              <Chip label={config.model} size="small" />
              <Chip label={`${config.memorySize} tokens`} size="small" />
              <Chip label={`T: ${config.temperature}`} size="small" />
            </Stack>
          </Box>
        </Stack>
      </DialogContent>

      <DialogActions className="p-6">
        <Button onClick={onClose} color="secondary">
          Cancel
        </Button>
        <Button 
          onClick={handleSave}
          variant="contained"
          color="primary"
          disabled={Object.keys(errors).length > 0}
        >
          Save Configuration
        </Button>
      </DialogActions>
    </Dialog>
  );
};