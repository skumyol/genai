import React from 'react';
import { Box, LinearProgress, Typography } from '@mui/material';

interface QuestionnaireProgressProps {
  currentSection: number;
  totalSections: number;
  currentQuestion: number;
  totalQuestions: number;
  title?: string;
}

export const QuestionnaireProgress: React.FC<QuestionnaireProgressProps> = ({
  currentSection,
  totalSections,
  currentQuestion,
  totalQuestions,
  title
}) => {
  const sectionProgress = totalSections > 0 ? (currentSection / totalSections) * 100 : 0;
  const questionProgress = totalQuestions > 0 ? (currentQuestion / totalQuestions) * 100 : 0;

  return (
    <Box sx={{ mb: 3 }}>
      {title && (
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
      )}
      
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Section {currentSection} of {totalSections}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {Math.round(sectionProgress)}%
          </Typography>
        </Box>
        <LinearProgress variant="determinate" value={sectionProgress} sx={{ height: 8, borderRadius: 4 }} />
      </Box>

      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Question {currentQuestion} of {totalQuestions}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {Math.round(questionProgress)}%
          </Typography>
        </Box>
        <LinearProgress 
          variant="determinate" 
          value={questionProgress} 
          sx={{ height: 6, borderRadius: 3 }}
          color="secondary"
        />
      </Box>
    </Box>
  );
};
