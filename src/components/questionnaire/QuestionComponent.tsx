import React from 'react';
import {
  FormControl,
  FormControlLabel,
  Radio,
  RadioGroup,
  TextField,
  Typography,
  Box,
  Divider
} from '@mui/material';
import { Question } from '../../types/schema';
import { QuestionType } from '../../types/enums';

interface QuestionComponentProps {
  question: Question;
  response: string | string[];
  onResponseChange: (response: string | string[]) => void;
  error?: string;
}

export const QuestionComponent: React.FC<QuestionComponentProps> = ({
  question,
  response,
  onResponseChange,
  error
}) => {
  const handleResponseChange = (value: string) => {
    onResponseChange(value);
  };

  if (question.type === QuestionType.BLOCK_HEADER) {
    return (
      <Box sx={{ my: 3 }}>
        <Divider sx={{ mb: 2 }} />
        <Typography variant="h6" component="h3" gutterBottom>
          {question.text}
        </Typography>
        <Divider sx={{ mt: 2 }} />
      </Box>
    );
  }

  if (question.type === QuestionType.MULTIPLE_CHOICE) {
    return (
      <Box sx={{ mb: 3 }}>
        <Typography variant="body1" component="label" gutterBottom>
          {question.text}
          {question.required && <Typography component="span" color="error"> *</Typography>}
        </Typography>
        <FormControl component="fieldset" fullWidth error={!!error}>
          <RadioGroup
            value={typeof response === 'string' ? response : ''}
            onChange={(e) => handleResponseChange(e.target.value)}
          >
            {question.choices?.map((choice, index) => (
              <FormControlLabel
                key={index}
                value={choice}
                control={<Radio />}
                label={choice}
                sx={{ mb: 1 }}
              />
            ))}
          </RadioGroup>
          {error && (
            <Typography variant="caption" color="error" sx={{ mt: 1 }}>
              {error}
            </Typography>
          )}
        </FormControl>
      </Box>
    );
  }

  if (question.type === QuestionType.TEXT_ENTRY) {
    return (
      <Box sx={{ mb: 3 }}>
        <Typography variant="body1" component="label" gutterBottom>
          {question.text}
          {question.required && <Typography component="span" color="error"> *</Typography>}
        </Typography>
        <TextField
          fullWidth
          multiline
          rows={3}
          value={typeof response === 'string' ? response : ''}
          onChange={(e) => handleResponseChange(e.target.value)}
          placeholder="Please share your thoughts..."
          error={!!error}
          helperText={error}
          sx={{ mt: 1 }}
        />
      </Box>
    );
  }

  return null;
};
