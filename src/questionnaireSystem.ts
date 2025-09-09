// Modular Questionnaire System Export
// This file exports all questionnaire components and utilities for easy reuse

// Core Components
export { QuestionComponent } from './components/questionnaire/QuestionComponent';
export { QuestionnaireRenderer } from './components/questionnaire/QuestionnaireRenderer';
export { QuestionnaireModal } from './components/questionnaire/QuestionnaireModal';
export { QuestionnaireProgress } from './components/questionnaire/QuestionnaireProgress';

// Utilities
export { QuestionnaireParser, loadQuestionnaireFromCSV } from './utils/questionnaireParser';

// Hooks
export { useQuestionnaire } from './hooks/useQuestionnaire';

// Redux
export { default as questionnaireReducer } from './store/questionnaireSlice';
export * from './store/questionnaireSlice';

// Types
export type {
  Question,
  QuestionnaireResponse,
  QuestionnaireSection,
  Questionnaire,
  UserStudyProgress,
  QuestionnaireState
} from './types/schema';

export {
  QuestionType,
  StudyPhase,
  QuestionnaireStatus
} from './types/enums';

// Example usage:
/*
import { 
  QuestionnaireModal, 
  useQuestionnaire, 
  QuestionType, 
  StudyPhase 
} from './questionnaireSystem';

// In your component:
const MyComponent = () => {
  const {
    currentQuestionnaire,
    currentResponses,
    isOpen,
    updateQuestionResponse,
    completeQuestionnaire,
    closeQuestionnaire
  } = useQuestionnaire();

  return (
    <QuestionnaireModal
      open={isOpen}
      questionnaire={currentQuestionnaire}
      responses={currentResponses}
      onResponseChange={updateQuestionResponse}
      onComplete={completeQuestionnaire}
      onClose={closeQuestionnaire}
    />
  );
};
*/
