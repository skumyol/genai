import { configureStore, createSlice, PayloadAction } from '@reduxjs/toolkit';
import { GameState, TimePeriod } from '../types/enums';
import { ChatFilters } from '../types/schema';
import questionnaireReducer from './questionnaireSlice';

interface GameStoreState {
  gameState: GameState;
  currentDay: number;
  numDays: number;
  currentTimePeriod: TimePeriod;
  selectedNPCId: string | null;
  playerNpcId: string | null;
  talkTargetNpcId: string | null;
  chatFilters: ChatFilters;
  isCharacterCreationOpen: boolean;
  isAdminPanelOpen: boolean;
}

const initialState: GameStoreState = {
  gameState: GameState.STOPPED,
  currentDay: 1,
  numDays: 1,
  currentTimePeriod: TimePeriod.MORNING,
  selectedNPCId: null,
  playerNpcId: null,
  talkTargetNpcId: null,
  chatFilters: {
    selectedDay: null,
    selectedTimePeriod: null,
    selectedNPCId: null
  },
  isCharacterCreationOpen: false,
  isAdminPanelOpen: false
};

const gameSlice = createSlice({
  name: 'game',
  initialState,
  reducers: {
    setGameState: (state, action: PayloadAction<GameState>) => {
      state.gameState = action.payload;
    },
    setCurrentDay: (state, action: PayloadAction<number>) => {
      state.currentDay = action.payload;
    },
    setNumDays: (state, action: PayloadAction<number>) => {
      state.numDays = action.payload;
    },
    setCurrentTimePeriod: (state, action: PayloadAction<TimePeriod>) => {
      state.currentTimePeriod = action.payload;
    },
    setSelectedNPCId: (state, action: PayloadAction<string | null>) => {
      state.selectedNPCId = action.payload;
    },
    setPlayerNpcId: (state, action: PayloadAction<string | null>) => {
      state.playerNpcId = action.payload;
      // Clear talk target if it equals newly selected player
      if (state.talkTargetNpcId && state.talkTargetNpcId === action.payload) {
        state.talkTargetNpcId = null;
      }
    },
    setTalkTargetNpcId: (state, action: PayloadAction<string | null>) => {
      state.talkTargetNpcId = action.payload;
    },
    setChatFilters: (state, action: PayloadAction<Partial<ChatFilters>>) => {
      state.chatFilters = { ...state.chatFilters, ...action.payload };
    },
    clearChatFilters: (state) => {
      state.chatFilters = {
        selectedDay: null,
        selectedTimePeriod: null,
        selectedNPCId: null
      };
    },
    setCharacterCreationOpen: (state, action: PayloadAction<boolean>) => {
      state.isCharacterCreationOpen = action.payload;
    },
    setAdminPanelOpen: (state, action: PayloadAction<boolean>) => {
      state.isAdminPanelOpen = action.payload;
    }
  }
});

export const {
  setGameState,
  setCurrentDay,
  setNumDays,
  setCurrentTimePeriod,
  setSelectedNPCId,
  setPlayerNpcId,
  setTalkTargetNpcId,
  setChatFilters,
  clearChatFilters,
  setCharacterCreationOpen,
  setAdminPanelOpen
} = gameSlice.actions;

export const store = configureStore({
  reducer: {
    game: gameSlice.reducer,
    questionnaire: questionnaireReducer
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types
        ignoredActions: ['persist/PERSIST', 'persist/REHYDRATE'],
        // Ignore these field paths in all actions (correct key is ignoredActionPaths)
        ignoredActionPaths: ['meta.arg', 'payload.timestamp'],
        // Ignore these paths in the state to avoid warnings while we migrate all timestamps to strings
        ignoredPaths: [
          'questionnaire.userProgress.responses',
          'questionnaire.userProgress.startedAt',
          'questionnaire.userProgress.completedAt',
          'questionnaire.currentResponses'
        ],
      },
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
