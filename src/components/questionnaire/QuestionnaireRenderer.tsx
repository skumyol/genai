import React, { useState, useMemo } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Stack,
  Alert
} from '@mui/material';
import { Question, QuestionnaireSection, QuestionnaireResponse } from '../../types/schema';
import { QuestionType } from '../../types/enums';
import { QuestionComponent } from './QuestionComponent';
import { QuestionnaireProgress } from './QuestionnaireProgress';

interface QuestionnaireRendererProps {
  sections: QuestionnaireSection[];
  title: string;
  description?: string;
  responses: QuestionnaireResponse[];
  onResponseChange: (questionId: string, response: string | string[]) => void;
  onComplete: () => void;
  onCancel?: () => void;
  isLoading?: boolean;
  showProgress?: boolean; // optional: hide progress UI if not desired
}

export const QuestionnaireRenderer: React.FC<QuestionnaireRendererProps> = ({
  sections,
  title,
  description,
  responses,
  onResponseChange,
  onComplete,
  onCancel,
  isLoading = false,
  showProgress = false
}) => {
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Calculate all questions across sections for progress tracking
  const allQuestions = useMemo(() => {
    return sections.flatMap(section => section.questions);
  }, [sections]);

  const respondableQuestions = useMemo(() => {
    return allQuestions.filter(q => q.type !== QuestionType.BLOCK_HEADER);
  }, [allQuestions]);

  const currentSection = sections[currentSectionIndex];
  const isLastSection = currentSectionIndex === sections.length - 1;

  // Get current question index for progress
  const currentQuestionIndex = useMemo(() => {
    let index = 0;
    for (let i = 0; i < currentSectionIndex; i++) {
      index += sections[i].questions.filter(q => q.type !== QuestionType.BLOCK_HEADER).length;
    }
    return index + 1; // 1-based for display
  }, [currentSectionIndex, sections]);

  const validateCurrentSection = (): boolean => {
    const newErrors: Record<string, string> = {};
    let isValid = true;

    if (!currentSection) return true;

    for (const question of currentSection.questions) {
      if (question.required && question.type !== QuestionType.BLOCK_HEADER) {
        const response = responses.find(r => r.questionId === question.id);
        if (!response || !response.response || response.response.toString().trim() === '') {
          newErrors[question.id] = 'This field is required';
          isValid = false;
        }
      }
    }

    setErrors(newErrors);
    return isValid;
  };

  const handleNext = () => {
    if (validateCurrentSection()) {
      if (isLastSection) {
        // Validate all sections before completing
        if (validateAllSections()) {
          onComplete();
        }
      } else {
        setCurrentSectionIndex(prev => prev + 1);
        setErrors({});
      }
    }
  };

  const validateAllSections = (): boolean => {
    const newErrors: Record<string, string> = {};
    let isValid = true;

    for (const question of respondableQuestions) {
      if (question.required) {
        const response = responses.find(r => r.questionId === question.id);
        if (!response || !response.response || response.response.toString().trim() === '') {
          newErrors[question.id] = 'This field is required';
          isValid = false;
        }
      }
    }

    setErrors(newErrors);
    
    if (!isValid) {
      // Find first section with error and navigate to it
      for (let i = 0; i < sections.length; i++) {
        const sectionHasError = sections[i].questions.some(q => newErrors[q.id]);
        if (sectionHasError) {
          setCurrentSectionIndex(i);
          break;
        }
      }
    }

    return isValid;
  };

  const handlePrevious = () => {
    if (currentSectionIndex > 0) {
      setCurrentSectionIndex(prev => prev - 1);
      setErrors({});
    }
  };

  const getResponseForQuestion = (questionId: string): string | string[] => {
    const response = responses.find(r => r.questionId === questionId);
    return response?.response || '';
  };

  if (!currentSection) {
    return (
      <Card>
        <CardContent>
          <Typography>No questions available</Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ maxWidth: 800, mx: 'auto' }}>
      <CardContent>
        {showProgress && (
          <QuestionnaireProgress
            currentSection={currentSectionIndex + 1}
            totalSections={sections.length}
            currentQuestion={currentQuestionIndex}
            totalQuestions={respondableQuestions.length}
            title={title}
          />
        )}

        {description && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            {description}
          </Typography>
        )}

        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom>
            {currentSection.title}
          </Typography>
          
          {currentSection.description && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {currentSection.description}
            </Typography>
          )}

          {Object.keys(errors).length > 0 && (
            <Alert severity="error" sx={{ mb: 2 }}>
              Please complete all required fields before proceeding.
            </Alert>
          )}

          {currentSection.questions.map((question) => (
            <QuestionComponent
              key={question.id}
              question={question}
              response={getResponseForQuestion(question.id)}
              onResponseChange={(response) => onResponseChange(question.id, response)}
              error={errors[question.id]}
            />
          ))}
        </Box>

        <Stack direction="row" spacing={2} justifyContent="space-between">
          <Box>
            {onCancel && (
              <Button variant="outlined" onClick={onCancel}>
                Cancel
              </Button>
            )}
          </Box>
          
          <Stack direction="row" spacing={2}>
            <Button
              variant="outlined"
              onClick={handlePrevious}
              disabled={currentSectionIndex === 0}
            >
              Previous
            </Button>
            
            <Button
              variant="contained"
              onClick={handleNext}
              disabled={isLoading}
            >
              {isLastSection ? 'Complete' : 'Next'}
            </Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};
