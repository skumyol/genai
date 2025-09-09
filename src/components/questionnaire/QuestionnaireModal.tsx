import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Box
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { Questionnaire, QuestionnaireResponse } from '../../types/schema';
import { QuestionnaireRenderer } from './QuestionnaireRenderer';

interface QuestionnaireModalProps {
  open: boolean;
  questionnaire: Questionnaire | null;
  responses: QuestionnaireResponse[];
  onResponseChange: (questionId: string, response: string | string[]) => void;
  onComplete: () => void;
  onClose: () => void;
  isLoading?: boolean;
  allowClose?: boolean;
}

export const QuestionnaireModal: React.FC<QuestionnaireModalProps> = ({
  open,
  questionnaire,
  responses,
  onResponseChange,
  onComplete,
  onClose,
  isLoading = false,
  allowClose = true
}) => {
  if (!questionnaire) return null;

  return (
    <Dialog
      open={open}
      onClose={allowClose ? onClose : undefined}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { minHeight: '60vh', maxHeight: '90vh' }
      }}
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>{questionnaire.title}</Box>
        {allowClose && (
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        )}
      </DialogTitle>
      
      <DialogContent>
        <QuestionnaireRenderer
          sections={questionnaire.sections}
          title=""
          description={questionnaire.description}
          responses={responses}
          onResponseChange={onResponseChange}
          onComplete={onComplete}
          onCancel={allowClose ? onClose : undefined}
          isLoading={isLoading}
        />
      </DialogContent>
    </Dialog>
  );
};
