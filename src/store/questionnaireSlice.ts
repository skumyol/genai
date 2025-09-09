import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { QuestionnaireState, Questionnaire, QuestionnaireResponse, UserStudyProgress } from '../types/schema';
import { StudyPhase } from '../types/enums';

const initialState: QuestionnaireState = {
  questionnaires: [],
  currentQuestionnaire: null,
  currentResponses: [],
  userProgress: null,
  isOpen: false,
  isLoading: false
};

const questionnaireSlice = createSlice({
  name: 'questionnaire',
  initialState,
  reducers: {
    setQuestionnaires: (state, action: PayloadAction<Questionnaire[]>) => {
      state.questionnaires = action.payload;
    },
    setCurrentQuestionnaire: (state, action: PayloadAction<Questionnaire | null>) => {
      state.currentQuestionnaire = action.payload;
      if (action.payload) {
        state.isOpen = true;
        // Initialize responses for all required questions
        state.currentResponses = action.payload.sections
          .flatMap(section => section.questions)
          .filter(q => q.required)
          .map(q => ({
            questionId: q.id,
            questionName: q.questionName,
            response: '',
            timestamp: new Date().toISOString()
          }));
      } else {
        state.currentResponses = [];
      }
    },
    setQuestionnaireOpen: (state, action: PayloadAction<boolean>) => {
      state.isOpen = action.payload;
      if (!action.payload) {
        state.currentQuestionnaire = null;
        state.currentResponses = [];
      }
    },
    setQuestionnaireLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload;
    },
    updateResponse: (state, action: PayloadAction<{ questionId: string; response: string | string[] }>) => {
      const { questionId, response } = action.payload;
      const existingIndex = state.currentResponses.findIndex(r => r.questionId === questionId);
      
      if (existingIndex >= 0) {
        state.currentResponses[existingIndex] = {
          ...state.currentResponses[existingIndex],
          response,
          timestamp: new Date().toISOString()
        };
      } else {
        // Find question name from current questionnaire
        const question = state.currentQuestionnaire?.sections
          .flatMap(s => s.questions)
          .find(q => q.id === questionId);
        
        state.currentResponses.push({
          questionId,
          questionName: question?.questionName,
          response,
          timestamp: new Date().toISOString()
        });
      }
    },
    setUserProgress: (state, action: PayloadAction<UserStudyProgress>) => {
      state.userProgress = action.payload;
    },
    updateUserProgress: (state, action: PayloadAction<Partial<UserStudyProgress>>) => {
      if (state.userProgress) {
        state.userProgress = { ...state.userProgress, ...action.payload };
      }
    },
    completeCurrentQuestionnaire: (state) => {
      if (state.currentQuestionnaire && state.userProgress) {
        // Add questionnaire to completed list
        if (!state.userProgress.completedQuestionnaires.includes(state.currentQuestionnaire.id)) {
          state.userProgress.completedQuestionnaires.push(state.currentQuestionnaire.id);
        }
        
        // Add responses to user progress
        state.userProgress.responses.push(...state.currentResponses);
        
        // Update phase if this was the final questionnaire
        if (state.currentQuestionnaire.phase === StudyPhase.FINAL_COMPARE) {
          state.userProgress.currentPhase = StudyPhase.COMPLETED;
          state.userProgress.completedAt = new Date().toISOString();
        }
      }
      
      // Close questionnaire
      state.isOpen = false;
      state.currentQuestionnaire = null;
      state.currentResponses = [];
    },
    initializeUserProgress: (state, action: PayloadAction<{ userId: string }>) => {
      state.userProgress = {
        userId: action.payload.userId,
        currentPhase: StudyPhase.PRE_GAME,
        completedQuestionnaires: [],
        sessionIds: {},
        messageCount: {},
        responses: [],
        startedAt: new Date().toISOString()
      };
    },
    incrementMessageCount: (state, action: PayloadAction<{ session: 'session1' | 'session2'; part: 'part1' | 'part2' }>) => {
      if (state.userProgress) {
        const { session, part } = action.payload;
        const key = `${session}${part.charAt(0).toUpperCase() + part.slice(1)}` as keyof typeof state.userProgress.messageCount;
        state.userProgress.messageCount[key] = (state.userProgress.messageCount[key] || 0) + 1;
      }
    },
    setSessionId: (state, action: PayloadAction<{ session: 'session1' | 'session2'; sessionId: string }>) => {
      if (state.userProgress) {
        state.userProgress.sessionIds[action.payload.session] = action.payload.sessionId;
      }
    },
    advancePhase: (state, action: PayloadAction<StudyPhase>) => {
      if (state.userProgress) {
        state.userProgress.currentPhase = action.payload;
      }
    },
    migrateTimestamps: (state) => {
      // Convert any Date objects to ISO strings for serialization compatibility
      if (state.userProgress) {
        // Convert userProgress timestamps
        if (state.userProgress.startedAt && typeof state.userProgress.startedAt !== 'string') {
          state.userProgress.startedAt = (state.userProgress.startedAt as any).toISOString();
        }
        if (state.userProgress.completedAt && typeof state.userProgress.completedAt !== 'string') {
          state.userProgress.completedAt = (state.userProgress.completedAt as any).toISOString();
        }
        
        // Convert response timestamps
        state.userProgress.responses = state.userProgress.responses.map(response => ({
          ...response,
          timestamp: typeof response.timestamp === 'string' 
            ? response.timestamp 
            : (response.timestamp as any).toISOString()
        }));
      }
      
      // Convert currentResponses timestamps
      state.currentResponses = state.currentResponses.map(response => ({
        ...response,
        timestamp: typeof response.timestamp === 'string' 
          ? response.timestamp 
          : (response.timestamp as any).toISOString()
      }));
    },
    resetQuestionnaireState: (state) => {
      // Preserve loaded questionnaires but reset per-user state
      state.currentQuestionnaire = null;
      state.currentResponses = [];
      state.userProgress = null;
      state.isOpen = false;
      state.isLoading = false;
    }
  }
});

export const {
  setQuestionnaires,
  setCurrentQuestionnaire,
  setQuestionnaireOpen,
  setQuestionnaireLoading,
  updateResponse,
  setUserProgress,
  updateUserProgress,
  completeCurrentQuestionnaire,
  initializeUserProgress,
  incrementMessageCount,
  setSessionId,
  advancePhase,
  migrateTimestamps,
  resetQuestionnaireState
} = questionnaireSlice.actions;

export default questionnaireSlice.reducer;
