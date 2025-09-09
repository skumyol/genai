// String formatting functions for the medieval game interface
import { 
  TimePeriod, 
  GameState, 
  NPCStatus, 
  AgentType, 
  AgentStatus, 
  ConnectionType, 
  LLMProvider 
} from '../types/enums';

export const formatDayNumber = (day: number): string => {
  return `Day ${day}`;
};

export const formatTimePeriod = (period: TimePeriod): string => {
  return period.charAt(0).toUpperCase() + period.slice(1);
};

export const formatGameState = (state: GameState): string => {
  switch (state) {
    case GameState.STOPPED:
      return 'Stopped';
    case GameState.RUNNING:
      return 'Running';
    case GameState.PAUSED:
      return 'Paused';
    default:
      return 'Unknown';
  }
};

export const formatNPCStatus = (status: NPCStatus): string => {
  switch (status) {
    case NPCStatus.ONLINE:
      return 'Online';
    case NPCStatus.OFFLINE:
      return 'Offline';
    case NPCStatus.BUSY:
      return 'Busy';
    default:
      return 'Unknown';
  }
};

export const formatMessageTime = (timestamp: Date): string => {
  return timestamp.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit',
    hour12: false 
  });
};

export const formatAgentType = (type: AgentType): string => {
  return type.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
};

export const formatAgentStatus = (status: AgentStatus): string => {
  return status.charAt(0).toUpperCase() + status.slice(1);
};

export const formatConnectionType = (type: ConnectionType): string => {
  return type.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
};

export const formatLLMProvider = (provider: LLMProvider): string => {
  return provider.toUpperCase();
};

export const formatNetworkComplexity = (agentCount: number, connectionCount: number): string => {
  const ratio = connectionCount / agentCount;
  if (ratio < 1) return 'Simple';
  if (ratio < 2) return 'Moderate';
  if (ratio < 3) return 'Complex';
  return 'Very Complex';
};