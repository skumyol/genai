// Type definitions for the medieval text-based game
import { 
  GameState, 
  TimePeriod, 
  NPCStatus, 
  MessageType, 
  AgentType,
  AgentStatus,
  ConnectionType,
  LLMProvider,
  NetworkValidationStatus,
  QuestionType,
  StudyPhase,
  QuestionnaireStatus
} from './enums';

// Props types (data passed to components)
export interface GameProps {
  initialGameState: GameState;
  wsEndpoint: string;
  apiEndpoint: string;
}

export interface NPCPanelProps {
  npcs: NPC[];
  selectedNPCId: string | null;
  onNPCSelect: (npcId: string) => void;
}

export interface ChatInterfaceProps {
  messages: Message[];
  selectedNPC: NPC | null;
  onSendMessage: (content: string, keystrokes?: number, approxTokens?: number) => void;
  isLoading: boolean;
}

export interface GameControlsProps {
  gameState: GameState;
  currentDay: number;
  currentTimePeriod: TimePeriod;
  numDays?: number;
  onNumDaysChange?: (value: number) => void;
  onStartGame: () => void;
  onStopGame: () => void;
  onContinueGame: () => void;
}

// Store types (global state data)
export interface GameStore {
  gameState: GameState;
  currentDay: number;
  numDays: number;
  currentTimePeriod: TimePeriod;
  selectedNPCId: string | null;
  chatFilters: ChatFilters;
  isCharacterCreationOpen: boolean;
  isAdminPanelOpen: boolean;
}

export interface ChatFilters {
  selectedDay: number | null;
  selectedTimePeriod: TimePeriod | null;
  selectedNPCId: string | null;
}

// Query types (API response data)
export interface NPC {
  id: string;
  name: string;
  status: NPCStatus;
  description: string;
  avatar: string;
}

export interface Message {
  id: string;
  type: MessageType;
  content: string;
  timestamp: Date;
  day: number;
  timePeriod: TimePeriod;
  npcId: string | null;
  npcName: string | null;
}

export interface GameStatus {
  currentDay: number;
  numDays: number;
  currentTimePeriod: TimePeriod;
  gameState: GameState;
}

export interface Character {
  id: string;
  name: string;
  background: string;
  role?: string; // Maps to character_properties.role in NPCMemory
  createdAt: Date;
}

// Agent network system type definitions
export interface AgentConfig {
  prompt: string;
  llmProvider: LLMProvider;
  model: string;
  endpointUrl: string;
  memorySize: number;
  temperature: number;
  maxTokens?: number;
  timeout?: number;
}

export interface Agent {
  id: string;
  type: AgentType;
  name: string;
  description?: string;
  position: { x: number; y: number };
  config: AgentConfig;
  status: AgentStatus;
  createdAt?: Date;
  lastModified?: Date;
}

export interface AgentConnection {
  id: string;
  sourceId: string;
  targetId: string;
  type: ConnectionType;
  strength: number;
  priority: number;
  metadata?: Record<string, any>;
}

export interface AgentNetwork {
  agents: Agent[];
  connections: AgentConnection[];
  metadata: {
    name: string;
    version: string;
    created: string;
    lastModified: string;
    description?: string;
  };
}

export interface AgentTemplate {
  id: string;
  type: AgentType;
  name: string;
  description: string;
  defaultConfig: AgentConfig;
  category?: string;
}

export interface NetworkValidation {
  status: NetworkValidationStatus;
  errors: string[];
  warnings: string[];
  suggestions: string[];
}

export interface NetworkStatistics {
  totalAgents: number;
  totalConnections: number;
  processingLayers: number;
  complexity: string;
  cycleCount: number;
  isolatedNodes: number;
}

export interface AgentNetworkBuilderProps {
  initialNetwork?: AgentNetwork;
  availableTemplates: AgentTemplate[];
  onNetworkChange: (network: AgentNetwork) => void;
  onExportNetwork: (network: AgentNetwork) => void;
  onValidationChange: (validation: NetworkValidation) => void;
  readonly?: boolean;
  maxAgents?: number;
  maxConnections?: number;
}

// Questionnaire system type definitions
export interface Question {
  id: string;
  type: QuestionType;
  text: string;
  choices?: string[];
  required?: boolean;
  questionName?: string;
  scoring?: string;
  block?: string;
}

export interface QuestionnaireResponse {
  questionId: string;
  questionName?: string;
  response: string | string[];
  timestamp: string; // ISO string instead of Date
}

export interface QuestionnaireSection {
  id: string;
  title: string;
  description?: string;
  questions: Question[];
}

export interface Questionnaire {
  id: string;
  title: string;
  description?: string;
  phase: StudyPhase;
  sections: QuestionnaireSection[];
  required: boolean;
}

export interface UserStudyProgress {
  userId: string;
  currentPhase: StudyPhase;
  completedQuestionnaires: string[];
  sessionIds: {
    session1?: string;
    session2?: string;
  };
  messageCount: {
    session1Part1?: number;
    session1Part2?: number;
    session2Part1?: number;
    session2Part2?: number;
  };
  responses: QuestionnaireResponse[];
  startedAt: string; // ISO string instead of Date
  completedAt?: string; // ISO string instead of Date
}

export interface QuestionnaireState {
  questionnaires: Questionnaire[];
  currentQuestionnaire: Questionnaire | null;
  currentResponses: QuestionnaireResponse[];
  userProgress: UserStudyProgress | null;
  isOpen: boolean;
  isLoading: boolean;
}
