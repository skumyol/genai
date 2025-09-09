// Mock data for the medieval text-based game
import { GameState, TimePeriod, NPCStatus, MessageType, CharacterClass } from '../types/enums';

// Data for global state store
export const mockStore = {
  gameState: GameState.STOPPED as const,
  currentDay: 1,
  numDays: 5,
  currentTimePeriod: TimePeriod.MORNING as const,
  selectedNPCId: null as string | null,
  chatFilters: {
    selectedDay: null as number | null,
    selectedTimePeriod: null as TimePeriod | null,
    selectedNPCId: null as string | null
  },
  isCharacterCreationOpen: false,
  isAdminPanelOpen: false
};

// Data returned by API queries  
export const mockQuery = {
  npcs: [
    {
      id: "npc-1",
      name: "Sir Gareth the Bold",
      status: NPCStatus.ONLINE as const,
      description: "A noble knight of the realm, known for his courage in battle",
      avatar: "https://i.pravatar.cc/150?img=1"
    },
    {
      id: "npc-2", 
      name: "Morgana the Wise",
      status: NPCStatus.ONLINE as const,
      description: "An ancient sorceress with knowledge of forgotten spells",
      avatar: "https://i.pravatar.cc/150?img=2"
    },
    {
      id: "npc-3",
      name: "Finn the Merchant",
      status: NPCStatus.BUSY as const,
      description: "A traveling trader with goods from distant lands",
      avatar: "https://i.pravatar.cc/150?img=3"
    },
    {
      id: "npc-4",
      name: "Brother Marcus",
      status: NPCStatus.OFFLINE as const,
      description: "A wise monk who tends to the monastery gardens",
      avatar: "https://i.pravatar.cc/150?img=4"
    },
    {
      id: "npc-5",
      name: "Lady Elara",
      status: NPCStatus.ONLINE as const,
      description: "A court noble with connections throughout the kingdom",
      avatar: "https://i.pravatar.cc/150?img=5"
    }
  ],
  messages: [
    {
      id: "msg-1",
      type: MessageType.SYSTEM as const,
      content: "Welcome to the realm! The adventure begins...",
      timestamp: new Date("2024-01-15T08:00:00Z"),
      day: 1,
      timePeriod: TimePeriod.MORNING as const,
      npcId: null,
      npcName: null
    },
    {
      id: "msg-2",
      type: MessageType.NPC as const,
      content: "Greetings, traveler! I am Sir Gareth. How may I assist you on this fine morning?",
      timestamp: new Date("2024-01-15T08:15:00Z"),
      day: 1,
      timePeriod: TimePeriod.MORNING as const,
      npcId: "npc-1",
      npcName: "Sir Gareth the Bold"
    },
    {
      id: "msg-3",
      type: MessageType.USER as const,
      content: "Hello Sir Gareth! I'm new to these lands. Can you tell me about this place?",
      timestamp: new Date("2024-01-15T08:16:00Z"),
      day: 1,
      timePeriod: TimePeriod.MORNING as const,
      npcId: "npc-1",
      npcName: null
    },
    {
      id: "msg-4",
      type: MessageType.NPC as const,
      content: "Ah, the ancient arts call to you! I sense great potential within your spirit.",
      timestamp: new Date("2024-01-15T12:30:00Z"),
      day: 1,
      timePeriod: TimePeriod.NOON as const,
      npcId: "npc-2",
      npcName: "Morgana the Wise"
    },
    {
      id: "msg-5",
      type: MessageType.USER as const,
      content: "Morgana, could you teach me about magic?",
      timestamp: new Date("2024-01-15T12:31:00Z"),
      day: 1,
      timePeriod: TimePeriod.NOON as const,
      npcId: "npc-2",
      npcName: null
    },
    {
      id: "msg-6",
      type: MessageType.SYSTEM as const,
      content: "Day 2 begins. The sun rises over the kingdom...",
      timestamp: new Date("2024-01-16T08:00:00Z"),
      day: 2,
      timePeriod: TimePeriod.MORNING as const,
      npcId: null,
      npcName: null
    }
  ],
  gameStatus: {
    currentDay: 1,
    numDays: 5,
    currentTimePeriod: TimePeriod.MORNING as const,
    gameState: GameState.STOPPED as const
  }
};

// Data passed as props to the root component
export const mockRootProps = {
  initialGameState: GameState.STOPPED as const,
  wsEndpoint: "ws://localhost:8080/game",
  apiEndpoint: "http://localhost:8080/api"
};