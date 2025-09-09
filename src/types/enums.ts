// Game state and UI enums for the medieval text-based game
export enum GameState {
  STOPPED = 'stopped',
  RUNNING = 'running',
  PAUSED = 'paused'
}

export enum TimePeriod {
  MORNING = 'morning',
  NOON = 'noon', 
  AFTERNOON = 'afternoon',
  EVENING = 'evening',
  NIGHT = 'night'
}

export enum NPCStatus {
  ONLINE = 'online',
  OFFLINE = 'offline',
  BUSY = 'busy'
}

export enum MessageType {
  USER = 'user',
  NPC = 'npc',
  SYSTEM = 'system'
}

// Agent system enums for hierarchical network management
export enum AgentType {
  NPC_MANAGER = 'npc_manager',
  OPINION = 'opinion',
  REPUTATION = 'reputation',
  SOCIAL_STANCE = 'social_stance',
  MEMORY = 'memory',
  CONTEXT = 'context',
  CUSTOM = 'custom'
}

export enum AgentStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  ERROR = 'error',
  PROCESSING = 'processing'
}

export enum ConnectionType {
  INFORMATION_FLOW = 'information_flow',
  DEPENDENCY = 'dependency',
  FEEDBACK = 'feedback',
  TRIGGER = 'trigger'
}

// Questionnaire system enums
export enum QuestionType {
  MULTIPLE_CHOICE = 'MC',
  TEXT_ENTRY = 'TE',
  BLOCK_HEADER = 'Block'
}

export enum StudyPhase {
  PRE_GAME = 'pre_game',
  SESSION_1 = 'session_1',
  SESSION_2 = 'session_2',
  FINAL_COMPARE = 'final_compare',
  COMPLETED = 'completed'
}

export enum QuestionnaireStatus {
  NOT_STARTED = 'not_started',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  SKIPPED = 'skipped'
}

export enum LLMProvider {
  OPENAI = 'openai',
  ANTHROPIC = 'anthropic',
  GOOGLE = 'google',
  CUSTOM = 'custom'
}

export enum NetworkValidationStatus {
  VALID = 'valid',
  INVALID = 'invalid',
  WARNING = 'warning',
  CHECKING = 'checking'
}

// Character creation related enums
export enum CharacterClass {
  WARRIOR = 'warrior',
  MAGE = 'mage',
  ROGUE = 'rogue',
  RANGER = 'ranger',
  CLERIC = 'cleric'
}

export enum Alignment {
  LAWFUL_GOOD = 'lawful_good',
  NEUTRAL_GOOD = 'neutral_good',
  CHAOTIC_GOOD = 'chaotic_good',
  LAWFUL_NEUTRAL = 'lawful_neutral',
  TRUE_NEUTRAL = 'true_neutral',
  CHAOTIC_NEUTRAL = 'chaotic_neutral',
  LAWFUL_EVIL = 'lawful_evil',
  NEUTRAL_EVIL = 'neutral_evil',
  CHAOTIC_EVIL = 'chaotic_evil'
}