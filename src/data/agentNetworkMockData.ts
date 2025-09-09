// Mock data for hierarchical agent network system
import { 
  AgentType, 
  AgentStatus, 
  ConnectionType, 
  LLMProvider 
} from '../types/enums';
import { 
  Agent, 
  AgentConnection, 
  AgentNetwork, 
  AgentTemplate 
} from '../types/schema';

export const mockAgentLibrary: AgentTemplate[] = [
  {
    id: 'template-npc-manager',
    type: AgentType.NPC_MANAGER,
    name: 'NPC Manager',
    description: 'Manages NPC behavior and interactions',
    defaultConfig: {
      prompt: 'You are an NPC manager responsible for coordinating character behaviors.',
      llmProvider: LLMProvider.OPENAI,
      model: 'gpt-4',
      endpointUrl: '/api/agents/npc-manager',
      memorySize: 1000,
      temperature: 0.7
    }
  },
  {
    id: 'template-opinion',
    type: AgentType.OPINION,
    name: 'Opinion Agent',
    description: 'Generates and manages character opinions',
    defaultConfig: {
      prompt: 'You analyze situations and form opinions based on character personality.',
      llmProvider: LLMProvider.OPENAI,
      model: 'gpt-3.5-turbo',
      endpointUrl: '/api/agents/opinion',
      memorySize: 500,
      temperature: 0.8
    }
  },
  {
    id: 'template-reputation',
    type: AgentType.REPUTATION,
    name: 'Reputation Agent',
    description: 'Tracks and manages character reputation',
    defaultConfig: {
      prompt: 'You track reputation changes and social standing.',
      llmProvider: LLMProvider.ANTHROPIC,
      model: 'claude-3-sonnet',
      endpointUrl: '/api/agents/reputation',
      memorySize: 2000,
      temperature: 0.5
    }
  },
  {
    id: 'template-social-stance',
    type: AgentType.SOCIAL_STANCE,
    name: 'Social Stance Agent',
    description: 'Manages character social positions and relationships',
    defaultConfig: {
      prompt: 'You determine social stances and relationship dynamics.',
      llmProvider: LLMProvider.OPENAI,
      model: 'gpt-4',
      endpointUrl: '/api/agents/social-stance',
      memorySize: 1500,
      temperature: 0.6
    }
  },
  {
    id: 'template-memory',
    type: AgentType.MEMORY,
    name: 'Memory Agent',
    description: 'Manages long-term and short-term memory for characters',
    defaultConfig: {
      prompt: 'You manage character memories and recall relevant information.',
      llmProvider: LLMProvider.GOOGLE,
      model: 'gemini-pro',
      endpointUrl: '/api/agents/memory',
      memorySize: 3000,
      temperature: 0.4
    }
  },
  {
    id: 'template-context',
    type: AgentType.CONTEXT,
    name: 'Context Agent',
    description: 'Provides situational context and environmental awareness',
    defaultConfig: {
      prompt: 'You provide contextual information about the current situation.',
      llmProvider: LLMProvider.OPENAI,
      model: 'gpt-4',
      endpointUrl: '/api/agents/context',
      memorySize: 800,
      temperature: 0.3
    }
  }
];

export const mockAgentNetwork: AgentNetwork = {
  agents: [
    {
      id: 'agent-1',
      type: AgentType.OPINION,
      name: 'Opinion Agent',
      description: 'Generates character opinions',
      position: { x: 100, y: 100 },
      config: {
        prompt: 'Generate character opinions based on interactions',
        llmProvider: LLMProvider.OPENAI,
        model: 'gpt-4',
        endpointUrl: '/api/agents/opinion',
        memorySize: 500,
        temperature: 0.8
      },
      status: AgentStatus.ACTIVE
    },
    {
      id: 'agent-2',
      type: AgentType.REPUTATION,
      name: 'Reputation Agent',
      description: 'Tracks character reputation',
      position: { x: 300, y: 150 },
      config: {
        prompt: 'Track and update character reputation',
        llmProvider: LLMProvider.ANTHROPIC,
        model: 'claude-3-sonnet',
        endpointUrl: '/api/agents/reputation',
        memorySize: 2000,
        temperature: 0.5
      },
      status: AgentStatus.ACTIVE
    },
    {
      id: 'agent-3',
      type: AgentType.SOCIAL_STANCE,
      name: 'Social Stance Agent',
      description: 'Manages social relationships',
      position: { x: 200, y: 250 },
      config: {
        prompt: 'Manage social relationships and stances',
        llmProvider: LLMProvider.OPENAI,
        model: 'gpt-4',
        endpointUrl: '/api/agents/social-stance',
        memorySize: 1500,
        temperature: 0.6
      },
      status: AgentStatus.ACTIVE
    },
    {
      id: 'agent-4',
      type: AgentType.NPC_MANAGER,
      name: 'NPC Manager',
      description: 'Coordinates NPC behaviors',
      position: { x: 400, y: 200 },
      config: {
        prompt: 'Coordinate and manage NPC behaviors',
        llmProvider: LLMProvider.OPENAI,
        model: 'gpt-4',
        endpointUrl: '/api/agents/npc-manager',
        memorySize: 1000,
        temperature: 0.7
      },
      status: AgentStatus.ACTIVE
    }
  ],
  connections: [
    {
      id: 'conn-1',
      sourceId: 'agent-1',
      targetId: 'agent-2',
      type: ConnectionType.INFORMATION_FLOW,
      strength: 0.8,
      priority: 1
    },
    {
      id: 'conn-2',
      sourceId: 'agent-2',
      targetId: 'agent-3',
      type: ConnectionType.DEPENDENCY,
      strength: 0.9,
      priority: 2
    },
    {
      id: 'conn-3',
      sourceId: 'agent-3',
      targetId: 'agent-4',
      type: ConnectionType.INFORMATION_FLOW,
      strength: 0.7,
      priority: 1
    },
    {
      id: 'conn-4',
      sourceId: 'agent-1',
      targetId: 'agent-4',
      type: ConnectionType.FEEDBACK,
      strength: 0.6,
      priority: 3
    }
  ],
  metadata: {
    name: 'Medieval Game Agent Network',
    version: '1.0.0',
    created: new Date().toISOString(),
    lastModified: new Date().toISOString(),
    description: 'Hierarchical agent network for medieval game NPCs'
  }
};