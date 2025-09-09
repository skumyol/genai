import { useSelector, useDispatch } from 'react-redux';
import { useEffect, useCallback } from 'react';
import { RootState } from '../store/gameStore';
import {
  setQuestionnaires,
  setCurrentQuestionnaire,
  setQuestionnaireOpen,
  updateResponse,
  completeCurrentQuestionnaire,
  initializeUserProgress,
  advancePhase,
  incrementMessageCount,
  setSessionId,
  migrateTimestamps
} from '../store/questionnaireSlice';
import { resetQuestionnaireState } from '../store/questionnaireSlice';
import { StudyPhase } from '../types/enums';
import { loadQuestionnaireFromCSV } from '../utils/questionnaireParser';

export const useQuestionnaire = () => {
  const dispatch = useDispatch();
  const questionnaireState = useSelector((state: RootState) => state.questionnaire);

  // Run migration for any existing Date objects in state
  useEffect(() => {
    dispatch(migrateTimestamps());
  }, [dispatch]);

  // Initialize questionnaires from CSV on first load
  useEffect(() => {
    const loadQuestionnaires = async () => {
      if (questionnaireState.questionnaires.length === 0) {
        try {
          const questionnaires = await loadQuestionnaireFromCSV();
          dispatch(setQuestionnaires(questionnaires));
        } catch (error) {
          console.error('Failed to load questionnaires:', error);
        }
      }
    };

    loadQuestionnaires();
  }, [dispatch, questionnaireState.questionnaires.length]);

  // Initialize user progress if not exists
  const initializeUser = useCallback((userId: string) => {
    if (!questionnaireState.userProgress) {
      dispatch(initializeUserProgress({ userId }));
    }
  }, [dispatch, questionnaireState.userProgress]);

  // Show questionnaire for specific phase
  const showQuestionnaire = useCallback((phase: StudyPhase) => {
    const questionnaire = questionnaireState.questionnaires.find(q => q.phase === phase);
    if (questionnaire) {
      dispatch(setCurrentQuestionnaire(questionnaire));
    }
  }, [dispatch, questionnaireState.questionnaires]);

  // Update response for a question
  const updateQuestionResponse = useCallback((questionId: string, response: string | string[]) => {
    dispatch(updateResponse({ questionId, response }));
  }, [dispatch]);

  // Complete current questionnaire
  const completeQuestionnaire = useCallback(() => {
    dispatch(completeCurrentQuestionnaire());
  }, [dispatch]);

  // Close questionnaire
  const closeQuestionnaire = useCallback(() => {
    dispatch(setQuestionnaireOpen(false));
  }, [dispatch]);

  // Track message sent (for message limit tracking)
  const trackMessage = useCallback((session: 'session1' | 'session2', part: 'part1' | 'part2') => {
    dispatch(incrementMessageCount({ session, part }));
  }, [dispatch]);

  // Set session ID for tracking
  const setStudySessionId = useCallback((session: 'session1' | 'session2', sessionId: string) => {
    dispatch(setSessionId({ session, sessionId }));
  }, [dispatch]);

  // Advance to next phase
  const advanceStudyPhase = useCallback((phase: StudyPhase) => {
    dispatch(advancePhase(phase));
  }, [dispatch]);

  // Reset questionnaire per-user state (for Reset All)
  const resetQuestionnaire = useCallback(() => {
    dispatch(resetQuestionnaireState());
  }, [dispatch]);

  // Check if questionnaire should be shown based on current state
  const shouldShowQuestionnaire = useCallback((messageLimit: number = 10): boolean => {
    const progress = questionnaireState.userProgress;
    if (!progress) return false;

    const { currentPhase, messageCount, completedQuestionnaires } = progress;

    // Check if pre-game questionnaire should be shown
    if (currentPhase === StudyPhase.PRE_GAME) {
      const preGameCompleted = completedQuestionnaires.includes('questionnaire_pre_game');
      return !preGameCompleted;
    }

    // Check session 1 questionnaire
    if (currentPhase === StudyPhase.SESSION_1) {
      const session1Completed = completedQuestionnaires.includes('questionnaire_session_1');
      const session1Messages = (messageCount.session1Part1 || 0) + (messageCount.session1Part2 || 0);
      return !session1Completed && session1Messages >= messageLimit;
    }

    // Check session 2 questionnaire
    if (currentPhase === StudyPhase.SESSION_2) {
      const session2Completed = completedQuestionnaires.includes('questionnaire_session_2');
      const session2Messages = (messageCount.session2Part1 || 0) + (messageCount.session2Part2 || 0);
      return !session2Completed && session2Messages >= messageLimit;
    }

    // Check final questionnaire
    if (currentPhase === StudyPhase.FINAL_COMPARE) {
      const finalCompleted = completedQuestionnaires.includes('questionnaire_final_compare');
      return !finalCompleted;
    }

    return false;
  }, [questionnaireState.userProgress]);

  // Get next questionnaire that should be shown
  const getNextQuestionnaire = useCallback((): StudyPhase | null => {
    const progress = questionnaireState.userProgress;
    if (!progress) return StudyPhase.PRE_GAME;

    const { currentPhase, completedQuestionnaires } = progress;

    // Check in order of study flow
    if (!completedQuestionnaires.includes('questionnaire_pre_game')) {
      return StudyPhase.PRE_GAME;
    }
    
    if (currentPhase === StudyPhase.SESSION_1 && !completedQuestionnaires.includes('questionnaire_session_1')) {
      return StudyPhase.SESSION_1;
    }
    
    if (currentPhase === StudyPhase.SESSION_2 && !completedQuestionnaires.includes('questionnaire_session_2')) {
      return StudyPhase.SESSION_2;
    }
    
    if (currentPhase === StudyPhase.FINAL_COMPARE && !completedQuestionnaires.includes('questionnaire_final_compare')) {
      return StudyPhase.FINAL_COMPARE;
    }

    return null;
  }, [questionnaireState.userProgress]);

  // Export user data for research
  const exportUserData = useCallback(() => {
    const progress = questionnaireState.userProgress;
    if (!progress) return null;

    return {
      userId: progress.userId,
      completedAt: progress.completedAt,
      phase: progress.currentPhase,
      responses: progress.responses,
      sessionIds: progress.sessionIds,
      messageCount: progress.messageCount,
      duration: progress.completedAt ? 
        new Date(progress.completedAt).getTime() - new Date(progress.startedAt).getTime() : 
        Date.now() - new Date(progress.startedAt).getTime()
    };
  }, [questionnaireState.userProgress]);

  return {
    // State
    questionnaires: questionnaireState.questionnaires,
    currentQuestionnaire: questionnaireState.currentQuestionnaire,
    currentResponses: questionnaireState.currentResponses,
    userProgress: questionnaireState.userProgress,
    isOpen: questionnaireState.isOpen,
    isLoading: questionnaireState.isLoading,

    // Actions
    initializeUser,
    showQuestionnaire,
    updateQuestionResponse,
    completeQuestionnaire,
    closeQuestionnaire,
    trackMessage,
    setStudySessionId,
    advanceStudyPhase,
    resetQuestionnaire,

    // Utilities
    shouldShowQuestionnaire,
    getNextQuestionnaire,
    exportUserData
  };
};
