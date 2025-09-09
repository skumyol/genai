import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../store/gameStore';
import {
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
} from '../store/gameStore';
import { GameState, TimePeriod } from '../types/enums';
import { ChatFilters } from '../types/schema';

export const useGameStore = () => {
  const dispatch = useDispatch<AppDispatch>();
  const gameState = useSelector((state: RootState) => state.game);

  return {
    // State selectors
    gameState: gameState.gameState,
    currentDay: gameState.currentDay,
    numDays: gameState.numDays,
    currentTimePeriod: gameState.currentTimePeriod,
    selectedNPCId: gameState.selectedNPCId,
    playerNpcId: gameState.playerNpcId,
    talkTargetNpcId: gameState.talkTargetNpcId,
    chatFilters: gameState.chatFilters,
    isCharacterCreationOpen: gameState.isCharacterCreationOpen,
    isAdminPanelOpen: gameState.isAdminPanelOpen,

    // Actions
    setGameState: (state: GameState) => dispatch(setGameState(state)),
    setCurrentDay: (day: number) => dispatch(setCurrentDay(day)),
    setNumDays: (numDays: number) => dispatch(setNumDays(numDays)),
    setCurrentTimePeriod: (period: TimePeriod) => dispatch(setCurrentTimePeriod(period)),
    setSelectedNPCId: (npcId: string | null) => dispatch(setSelectedNPCId(npcId)),
    setPlayerNpcId: (npcId: string | null) => dispatch(setPlayerNpcId(npcId)),
    setTalkTargetNpcId: (npcId: string | null) => dispatch(setTalkTargetNpcId(npcId)),
    setChatFilters: (filters: Partial<ChatFilters>) => dispatch(setChatFilters(filters)),
    clearChatFilters: () => dispatch(clearChatFilters()),
    setCharacterCreationOpen: (open: boolean) => dispatch(setCharacterCreationOpen(open)),
    setAdminPanelOpen: (open: boolean) => dispatch(setAdminPanelOpen(open))
  };
};
